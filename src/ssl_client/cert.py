"""证书申请和管理模块"""

import time
import os
import zipfile
import io
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from .config import Config
from .api import APIClient, APIError


console = Console()

# 证书价格
CERT_PRICES = {
    'single': 100,
    'wildcard': 200,
}


class CertManager:
    """证书管理器"""

    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def parse_domain_input(self, domain_input: str) -> Dict[str, str]:
        """
        解析用户输入的域名

        Args:
            domain_input: 用户输入的域名
                - www.example.com -> single, domain=example.com, prefix=www
                - *.example.com -> wildcard, domain=example.com, prefix=*
                - example.com -> single, domain=example.com, prefix=www

        Returns:
            {domain, prefix, cert_type}
        """
        domain_input = domain_input.strip().lower()

        # 泛域名
        if domain_input.startswith('*.'):
            root_domain = domain_input[2:]
            return {
                'domain': root_domain,
                'prefix': '*',
                'cert_type': 'wildcard',
            }

        # 单域名（可能带 www 前缀或直接是根域名）
        parts = domain_input.split('.')
        if len(parts) >= 2:
            if len(parts) == 2:
                # example.com -> www.example.com
                return {
                    'domain': domain_input,
                    'prefix': 'www',
                    'cert_type': 'single',
                }
            else:
                # www.example.com 或 sub.example.com
                prefix = parts[0]
                domain = '.'.join(parts[1:])
                return {
                    'domain': domain,
                    'prefix': prefix,
                    'cert_type': 'single',
                }

        raise ValueError(f"无效的域名格式: {domain_input}")

    def check_coins(self, required_coins: int) -> bool:
        """
        检查金币是否足够

        Returns:
            是否足够
        """
        current_coins = self.api.get_coins()
        console.print(f"[yellow]当前金币: {current_coins}，需要: {required_coins}[/yellow]")
        return current_coins >= required_coins

    def apply_single_cert(self, domain: str, prefix: str) -> Optional[int]:
        """
        申请单域名证书（HTTP验证）

        Args:
            domain: 根域名
            prefix: 前缀

        Returns:
            task_id 或 None
        """
        console.print(f"\n[cyan]正在申请单域名证书: {prefix}.{domain}[/cyan]")

        try:
            result = self.api.apply_certificate(
                domain=domain,
                cert_type='single',
                verify_method='http',
                prefix=prefix,
            )
            task_id = result.get('task_id')
            if task_id:
                console.print(f"[green]✓ 证书申请已提交，任务ID: {task_id}[/green]")
                return task_id
            else:
                console.print(f"[red]申请失败：{result.get('message', '未知错误')}[/red]")
                return None
        except APIError as e:
            console.print(f"[red]申请失败: {e}[/red]")
            return None

    def apply_wildcard_cert(
        self,
        domain: str,
        dns_provider: str,
        dns_key_id: str,
        dns_key_secret: str,
    ) -> Optional[int]:
        """
        申请泛域名证书（DNS验证）

        Args:
            domain: 根域名
            dns_provider: DNS服务商
            dns_key_id: DNS API密钥ID
            dns_key_secret: DNS API密钥Secret

        Returns:
            task_id 或 None
        """
        console.print(f"\n[cyan]正在申请泛域名证书: *.{domain}[/cyan]")
        console.print(f"[dim]DNS服务商: {dns_provider}[/dim]")

        try:
            result = self.api.apply_certificate(
                domain=domain,
                cert_type='wildcard',
                verify_method='dns',
                prefix='*',
                dns_provider=dns_provider,
                dns_key_id=dns_key_id,
                dns_key_secret=dns_key_secret,
            )
            task_id = result.get('task_id')
            if task_id:
                console.print(f"[green]✓ 证书申请已提交，任务ID: {task_id}[/green]")
                return task_id
            else:
                console.print(f"[red]申请失败：{result.get('message', '未知错误')}[/red]")
                return None
        except APIError as e:
            console.print(f"[red]申请失败: {e}[/red]")
            return None

    def poll_task_status(self, task_id: int) -> Dict[str, Any]:
        """
        轮询任务状态直到完成或失败

        使用 rich progress 显示进度

        Returns:
            {status, ...} 任务结果
        """
        status_descriptions = {
            'pending': '⏳ 等待处理...',
            'processing': '🔄 正在申请证书...',
            'waiting_verify': '🔍 等待验证...',
            'completed': '✅ 证书申请完成',
            'error': '❌ 申请失败',
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("正在申请请稍后...", total=None)

            while True:
                try:
                    result = self.api.get_task_status(task_id)
                    status = result.get('status', 'pending')
                    description = status_descriptions.get(
                        status, f'未知状态: {status}'
                    )

                    progress.update(task, description=description)

                    if status == 'completed':
                        # 证书申请完成
                        progress.update(
                            task,
                            description="[green]证书申请完成，正在下载...[/green]"
                        )
                        return result

                    elif status == 'error':
                        error_msg = result.get('error_msg', '未知错误')
                        progress.update(
                            task,
                            description=f"[red]申请失败: {error_msg}[/red]"
                        )
                        return result

                    elif status == 'waiting_verify':
                        progress.update(
                            task,
                            description="[yellow]等待域名验证...[/yellow]"
                        )

                except APIError as e:
                    progress.update(
                        task,
                        description=f"[red]查询状态失败: {e}[/red]"
                    )

                time.sleep(3)

    def download_certificate(self, task_id: int, domain_label: str) -> Optional[str]:
        """
        下载证书到本地

        Args:
            task_id: 任务ID
            domain_label: 用于文件名的域名标签

        Returns:
            证书zip文件路径 或 None
        """
        # 确定保存目录
        cert_dir = self.config.get_config_dir() / 'certs'
        cert_dir.mkdir(parents=True, exist_ok=True)

        # 清理域名中的特殊字符作为文件名
        safe_name = domain_label.replace('*', 'wildcard').replace('.', '_')
        zip_path = str(cert_dir / f'{safe_name}.zip')

        try:
            console.print("[cyan]正在下载证书...[/cyan]")
            self.api.download_certificate(task_id, zip_path)
            console.print(f"[green]✓ 证书已下载到: {zip_path}[/green]")
            return zip_path
        except APIError as e:
            console.print(f"[red]下载证书失败: {e}[/red]")
            return None

    def show_cert_info(self, zip_path: str, domain_label: str):
        """
        显示证书信息和解压说明
        """
        console.print(Panel.fit(
            f"[bold green]证书申请完成！[/bold green]\n\n"
            f"域名: {domain_label}\n"
            f"证书文件: {zip_path}\n\n"
            f"[bold]解压后包含以下文件：[/bold]\n"
            f"  - fullchain.pem  (完整证书链)\n"
            f"  - privkey.pem    (私钥文件)\n"
            f"  - cert.pem       (证书文件)\n\n"
            f"[dim]解压命令: unzip {zip_path} -d ./{domain_label}_cert/[/dim]",
            title="📜 证书信息",
        ))
