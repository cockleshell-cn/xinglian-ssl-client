"""证书安装模块 - 下载后安装到系统"""

import os
import zipfile
import shutil
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


console = Console()


class CertInstaller:
    """证书安装器"""

    def __init__(self):
        pass

    def extract_certificate(self, zip_path: str, domain_label: str) -> Optional[str]:
        """
        解压证书到本地目录

        Args:
            zip_path: 证书zip文件路径
            domain_label: 域名标签

        Returns:
            解压目录路径 或 None
        """
        # 确定解压目录
        parent_dir = Path(zip_path).parent
        extract_dir = parent_dir / domain_label.replace('*', 'wildcard').replace('.', '_')

        try:
            # 清理已存在的目录
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(str(extract_dir))

            console.print(f"[green]✓ 证书已解压到: {extract_dir}[/green]")
            return str(extract_dir)

        except Exception as e:
            console.print(f"[red]解压证书失败: {e}[/red]")
            return None

    def print_cert_info(self, cert_dir: str, domain: str):
        """
        打印证书文件信息和安装指引
        """
        cert_dir_path = Path(cert_dir)

        if not cert_dir_path.exists():
            console.print("[red]证书目录不存在[/red]")
            return

        files = list(cert_dir_path.iterdir())

        table = Table(title=f"📜 证书文件 - {domain}", box=None)
        table.add_column("文件名", style="cyan")
        table.add_column("大小", style="yellow")
        table.add_column("说明", style="white")

        for f in sorted(files):
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f} MB"

            desc = {
                'fullchain.pem': '完整证书链（Nginx配置用这个）',
                'privkey.pem': '私钥文件（请妥善保管）',
                'cert.pem': '证书文件',
                'chain.pem': '中间证书链',
            }.get(f.name, '')

            table.add_row(f.name, size_str, desc)

        console.print(table)

        # Nginx 配置示例
        console.print(Panel.fit(
            "[bold]Nginx 配置示例：[/bold]\n\n"
            f"server {{\n"
            f"    listen 443 ssl;\n"
            f"    server_name {domain};\n\n"
            f"    ssl_certificate     {cert_dir}/fullchain.pem;\n"
            f"    ssl_certificate_key {cert_dir}/privkey.pem;\n\n"
            f"    # ... 其余配置 ...\n"
            f"}}",
            title="🔧 Nginx 配置",
        ))

    def install_to_nginx(self, cert_dir: str, domain: str) -> bool:
        """
        尝试自动安装证书到 Nginx 目录

        Args:
            cert_dir: 证书目录
            domain: 域名

        Returns:
            是否成功
        """
        # Nginx 证书目录
        nginx_ssl_dirs = [
            '/etc/nginx/ssl',
            '/etc/ssl/nginx',
            '/etc/letsencrypt/live',
        ]

        target_dir = None
        for d in nginx_ssl_dirs:
            d_path = Path(d)
            if d_path.exists() and d_path.is_dir():
                target_dir = d_path / domain
                break

        if target_dir is None:
            console.print("[yellow]未找到Nginx SSL证书目录，请手动安装证书[/yellow]")
            return False

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            cert_path = Path(cert_dir)

            for f in cert_path.iterdir():
                if f.is_file():
                    shutil.copy2(str(f), str(target_dir / f.name))

            console.print(f"[green]✓ 证书已安装到: {target_dir}[/green]")
            return True

        except PermissionError:
            console.print(
                f"[red]权限不足，无法安装到 {target_dir}[/red]\n"
                f"[yellow]请使用 sudo 运行或手动复制证书文件[/yellow]"
            )
            return False
        except Exception as e:
            console.print(f"[red]安装证书失败: {e}[/red]")
            return False
