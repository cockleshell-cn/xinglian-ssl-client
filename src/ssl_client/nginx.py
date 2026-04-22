"""Nginx配置管理模块 - 支持Windows/Linux/macOS"""

import os
import time
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from rich.console import Console


console = Console()


class NginxManager:
    """Nginx配置管理器"""

    ACME_CONFIG_NAME = "xinglian-acme.conf"

    def __init__(self):
        self.nginx_config_dir = self._find_nginx_config_dir()
        self.nginx_executable = self._find_nginx_executable()

    def _find_nginx_config_dir(self) -> Optional[Path]:
        """查找Nginx配置目录（跨平台）"""
        if os.name == 'nt':  # Windows
            common_paths = [
                "C:\\nginx\\conf\\conf.d",
                "C:\\Program Files\\nginx\\conf\\conf.d",
                "C:\\tools\\nginx\\conf\\conf.d",
            ]
        else:  # Linux/macOS
            common_paths = [
                "/etc/nginx/conf.d",              # Linux常见路径
                "/etc/nginx/sites-enabled",        # Debian/Ubuntu
                "/usr/local/nginx/conf/conf.d",    # 编译安装
                "/opt/homebrew/etc/nginx/servers", # macOS Homebrew
                "/usr/local/etc/nginx/servers",    # macOS (另一种)
            ]

        for path in common_paths:
            if os.path.isdir(path):
                return Path(path)

        return None

    def _find_nginx_executable(self) -> Optional[str]:
        """查找Nginx可执行文件"""
        nginx_cmd = shutil.which("nginx")

        if not nginx_cmd and os.name == 'nt':
            # Windows 下尝试常见路径
            common_paths = [
                "C:\\nginx\\nginx.exe",
                "C:\\Program Files\\nginx\\nginx.exe",
                "C:\\tools\\nginx\\nginx.exe",
            ]
            for path in common_paths:
                if os.path.isfile(path):
                    nginx_cmd = path
                    break

        return nginx_cmd

    def is_nginx_available(self) -> bool:
        """检查Nginx是否可用"""
        return self.nginx_executable is not None and self.nginx_config_dir is not None

    def create_acme_proxy_config(self, domain: str) -> bool:
        """
        创建ACME验证反向代理配置

        Args:
            domain: 完整域名

        Returns:
            是否成功
        """
        if not self.is_nginx_available():
            console.print("[red]未找到Nginx，无法使用HTTP验证[/red]")
            return False

        config_content = f"""server {{
    listen 80;
    server_name {domain};

    # ACME验证路径 - 星链下载SSL客户端自动生成
    location /.well-known/acme-challenge/ {{
        proxy_pass https://www.cockleshell.cn/.well-known/acme-challenge/;
        proxy_set_header Host www.cockleshell.cn;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""

        config_path = self.nginx_config_dir / self.ACME_CONFIG_NAME

        try:
            with open(config_path, 'w') as f:
                f.write(config_content)
            console.print(f"[green]✓ 已创建Nginx配置: {config_path}[/green]")
            return True
        except PermissionError:
            console.print(
                f"[red]权限不足，无法写入 {config_path}[/red]\n"
                f"[yellow]请使用 sudo 运行此客户端，或手动创建以下配置：[/yellow]\n"
                f"{config_content}"
            )
            return False
        except Exception as e:
            console.print(f"[red]创建Nginx配置失败: {e}[/red]")
            return False

    def remove_acme_proxy_config(self) -> bool:
        """删除ACME验证配置"""
        if self.nginx_config_dir is None:
            return False

        config_path = self.nginx_config_dir / self.ACME_CONFIG_NAME

        if config_path.exists():
            try:
                config_path.unlink()
                console.print(f"[green]✓ 已删除Nginx配置: {config_path}[/green]")
                return True
            except PermissionError:
                console.print(f"[red]权限不足，无法删除 {config_path}[/red]")
                return False
            except Exception as e:
                console.print(f"[red]删除Nginx配置失败: {e}[/red]")
                return False

        return True

    def reload_nginx(self) -> bool:
        """重载Nginx配置"""
        if self.nginx_executable is None:
            console.print("[red]未找到Nginx可执行文件[/red]")
            return False

        try:
            # 先测试配置
            result = subprocess.run(
                [self.nginx_executable, "-t"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                console.print(f"[red]Nginx配置测试失败:[/red]")
                console.print(f"[red]{result.stderr}[/red]")
                return False

            # 重载配置
            result = subprocess.run(
                [self.nginx_executable, "-s", "reload"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                console.print(f"[red]Nginx重载失败: {result.stderr}[/red]")
                return False

            console.print("[green]✓ Nginx配置已重载[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Nginx操作失败: {e}[/red]")
            return False

    def verify_acme_proxy(self, domain: str, max_retries: int = 5) -> bool:
        """
        验证ACME反向代理是否生效

        Args:
            domain: 域名
            max_retries: 最大重试次数

        Returns:
            是否验证成功
        """
        import requests

        test_url = f"http://{domain}/.well-known/acme-challenge/test"

        console.print(f"[dim]验证反向代理: {test_url}[/dim]")

        for i in range(max_retries):
            try:
                time.sleep(2)  # 等待配置生效
                response = requests.get(test_url, timeout=10, allow_redirects=False)

                # 只要能访问到服务器就算成功（可能返回404，但说明代理生效）
                if response.status_code in [200, 301, 302, 404]:
                    console.print(f"[green]✓ 反向代理验证成功 (HTTP {response.status_code})[/green]")
                    return True

            except requests.exceptions.RequestException as e:
                console.print(f"[dim]第{i+1}次验证失败: {e}[/dim]")

        console.print("[red]反向代理验证失败，请检查Nginx配置[/red]")
        return False

    def setup_acme_proxy(self, domain: str) -> bool:
        """
        设置ACME反向代理（完整流程）

        Args:
            domain: 域名

        Returns:
            是否成功
        """
        console.print(f"\n[cyan]配置ACME验证反向代理...[/cyan]")

        # 1. 创建配置
        if not self.create_acme_proxy_config(domain):
            return False

        # 2. 重载Nginx
        if not self.reload_nginx():
            self.remove_acme_proxy_config()
            return False

        # 3. 验证代理
        if not self.verify_acme_proxy(domain):
            console.print("[red]反向代理验证失败，清理配置并退出...[/red]")
            self.remove_acme_proxy_config()
            self.reload_nginx()
            return False

        return True

    def cleanup_acme_proxy(self):
        """清理ACME反向代理配置"""
        self.remove_acme_proxy_config()
        self.reload_nginx()
