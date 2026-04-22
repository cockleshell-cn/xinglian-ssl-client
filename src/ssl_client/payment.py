"""支付/充值模块 - 金币充值、二维码、余额轮询"""

import io
import time
import threading
import webbrowser
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import Config
from .api import APIClient, APIError


console = Console()

# 最小充值套餐ID（100金币=10元）
MIN_PACKAGE_ID = 1


class PaymentManager:
    """支付管理器"""

    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client
        self._stop_polling = False

    def show_packages_and_create_order(self) -> Optional[str]:
        """
        展示充值套餐并让用户选择，返回支付链接 pay_url
        用户也可以选择退出
        """
        try:
            result = self.api.get_packages()
            packages = result.get('packages', [])
        except APIError as e:
            console.print(f"[red]获取充值套餐失败: {e}[/red]")
            return None

        if not packages:
            console.print("[red]暂无可用的充值套餐[/red]")
            return None

        # 展示套餐
        table = Table(title="💰 金币充值套餐", box=None)
        table.add_column("编号", style="cyan")
        table.add_column("套餐", style="yellow")
        table.add_column("价格", style="green")
        table.add_column("赠送", style="magenta")

        for pkg in packages:
            bonus_str = f"+{pkg.get('bonus', 0)}" if pkg.get('bonus') else "-"
            table.add_row(
                str(pkg['id']),
                pkg.get('name', f"{pkg['coins']}金币"),
                f"¥{pkg['price']}",
                bonus_str
            )

        console.print(table)
        console.print()

        # 让用户选择
        while True:
            choice = Prompt.ask(
                "请选择充值套餐编号（输入编号创建订单，输入 q 退出充值）",
                default=""
            )
            if choice.lower() in ('q', 'quit', 'exit', ''):
                return None

            try:
                pkg_id = int(choice)
                if any(p['id'] == pkg_id for p in packages):
                    break
                console.print("[red]无效的套餐编号，请重新选择[/red]")
            except ValueError:
                console.print("[red]请输入数字编号[/red]")

        # 创建订单
        try:
            console.print("[dim]正在创建订单...[/dim]")
            order = self.api.create_order(pkg_id)
            pay_url = order.get('pay_url', '')
            if not pay_url:
                console.print("[red]创建订单失败：未获取到支付链接[/red]")
                return None

            console.print(f"\n[green]✓ 订单已创建[/green]")
            console.print(f"   订单号: {order.get('order_no', '')}")
            console.print(f"   金额: ¥{order.get('amount', '')}")
            console.print(f"   获得金币: {order.get('coins', '')}")

            return order

        except APIError as e:
            console.print(f"[red]创建订单失败: {e}[/red]")
            return None

    def show_recharge_qrcode(self, pay_url: str):
        """显示支付二维码"""
        try:
            import qrcode
            from rich.text import Text

            console.print("\n[bold cyan]请使用支付宝扫码支付：[/bold cyan]\n")

            # 生成二维码
            qr = qrcode.QRCode(box_size=2, border=1)
            qr.add_data(pay_url)
            qr.make(fit=True)

            # 在终端打印二维码
            qr_matrix = qr.get_matrix()
            for row in qr_matrix:
                line = ''
                for cell in row:
                    line += '██' if cell else '  '
                console.print(line)

            console.print(f"\n[dim]或复制链接到浏览器打开：[/dim]")
            console.print(f"[blue underline]{pay_url}[/blue underline]")

            # 尝试自动打开浏览器
            try:
                webbrowser.open(pay_url)
                console.print("[dim]已自动打开浏览器...[/dim]")
            except Exception:
                pass

        except ImportError:
            console.print(f"\n[bold cyan]请使用支付宝扫码支付：[/bold cyan]")
            console.print(f"[blue underline]{pay_url}[/blue underline]")
            try:
                webbrowser.open(pay_url)
            except Exception:
                pass

    def wait_for_coins(self, required_coins: int) -> bool:
        """
        轮询等待金币到账
        返回 True 表示金币已足够，False 表示用户取消
        """
        console.print(f"\n[bold yellow]⏳ 等待金币到账...（需要至少 {required_coins} 金币）[/bold yellow]")
        console.print("[dim]支付完成后，系统会自动检测到账[/dim]")
        console.print("[dim]按 Ctrl+C 可退出等待[/dim]\n")

        self._stop_polling = False

        try:
            while not self._stop_polling:
                try:
                    current_coins = self.api.get_coins()
                    if current_coins >= required_coins:
                        console.print(f"\n[green]✓ 金币已到账！当前金币: {current_coins}[/green]")
                        return True

                    console.print(
                        f"[dim]当前金币: {current_coins}/{required_coins} "
                        f"等待中... (5秒后重试)[/dim]"
                    )

                except APIError as e:
                    console.print(f"[dim]查询失败: {e}，5秒后重试...[/dim]")

                # 等待5秒
                for _ in range(5):
                    if self._stop_polling:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            console.print("\n[yellow]用户取消等待[/yellow]")
            return False

        return False

    def handle_insufficient_coins(self, required_coins: int) -> bool:
        """
        处理金币不足的情况
        1. 展示充值套餐
        2. 让用户选择
        3. 显示支付二维码
        4. 轮询等待到账
        返回 True 表示充值成功，False 表示用户取消
        """
        console.print(f"\n[red]⚠ 金币不足！需要 {required_coins} 金币[/red]")

        # 创建订单
        order = self.show_packages_and_create_order()
        if not order:
            return False

        pay_url = order.get('pay_url', '')
        if pay_url:
            self.show_recharge_qrcode(pay_url)

        # 轮询等待到账
        return self.wait_for_coins(required_coins)

    def stop_polling(self):
        """停止轮询"""
        self._stop_polling = True
