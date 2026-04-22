"""用户认证模块 - 通过短信验证码登录/注册获取api_token"""

import re
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from .config import Config
from .api import APIClient, APIError


console = Console()


class AuthManager:
    """用户认证管理器"""

    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def ensure_authenticated(self) -> bool:
        """确保用户已认证，返回是否成功"""
        if self.config.has_api_token():
            # 验证api_token是否有效
            try:
                self.api.verify_api_token(self.config.api_token)
                return True
            except APIError:
                console.print("[yellow]API Token无效，请重新登录[/yellow]")
                self.config.api_token = ""

        # 需要登录或注册
        return self.login_or_register()

    def login_or_register(self) -> bool:
        """登录或注册流程"""
        console.print(Panel.fit(
            "[bold cyan]欢迎使用星链下载SSL证书客户端[/bold cyan]\n"
            "请先登录或注册账号（仅需手机号+验证码）",
            title="🔐 用户认证",
        ))

        # 输入手机号
        while True:
            phone = Prompt.ask("请输入手机号")
            if self._validate_phone(phone):
                break
            console.print("[red]手机号格式不正确，请重新输入[/red]")

        # 发送验证码
        try:
            console.print("[dim]正在发送验证码...[/dim]")
            self.api.send_sms_code(phone)
            console.print(f"[green]验证码已发送到 {phone}[/green]")
        except APIError as e:
            console.print(f"[red]发送验证码失败: {e}[/red]")
            return False

        # 输入验证码
        code = Prompt.ask("请输入验证码")

        # 登录或注册
        try:
            console.print("[dim]正在验证...[/dim]")
            result = self.api.login_or_register(phone, code)

            api_token = result.get('api_token')
            if api_token:
                self.config.api_token = api_token
                self.api.config.api_token = api_token
                self.config.save()

                is_new_user = result.get('is_new_user', False)
                if is_new_user:
                    coins = result.get('user', {}).get('coins', 100)
                    console.print(f"[green]注册成功！新用户赠送 {coins} 金币[/green]")
                else:
                    console.print("[green]登录成功！[/green]")

                return True
            else:
                console.print("[red]登录失败：未获取到api_token[/red]")
                return False

        except APIError as e:
            console.print(f"[red]登录失败: {e}[/red]")
            return False

    def show_coins(self):
        """显示用户金币"""
        try:
            coins = self.api.get_coins()
            console.print(f"\n[yellow]💰 当前金币: {coins}[/yellow]\n")
        except APIError:
            console.print("[red]获取金币失败[/red]")

    def _validate_phone(self, phone: str) -> bool:
        """验证手机号格式"""
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))
