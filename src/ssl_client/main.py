#!/usr/bin/env python3
"""
星链下载SSL证书客户端
支持 Windows / Linux / macOS
"""

import sys
import time
import signal
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .api import APIClient, APIError, AuthenticationError
from .auth import AuthManager
from .cert import CertManager, CERT_PRICES
from .payment import PaymentManager
from .nginx import NginxManager
from .verify import (
    check_domain_resolution,
    wait_for_domain_resolution,
    verify_reverse_proxy,
    get_public_ip,
)
from .installer import CertInstaller


console = Console()

# 证书价格常量
SINGLE_CERT_COINS = CERT_PRICES['single']    # 100
WILDCARD_CERT_COINS = CERT_PRICES['wildcard']  # 200


def print_banner():
    """打印启动横幅"""
    console.print(Panel.fit(
        "[bold cyan]★ 星链下载SSL证书客户端 ★[/bold cyan]\n"
        "[dim]自动申请免费SSL证书 | 支持单域名/泛域名[/dim]",
        title="🔒 SSL Certificate Tool",
        border_style="cyan",
    ))


def handle_interrupt(signum, frame):
    """处理 Ctrl+C"""
    console.print("\n[yellow]用户退出[/yellow]")
    sys.exit(0)


def main():
    """主函数"""
    signal.signal(signal.SIGINT, handle_interrupt)

    print_banner()

    # 加载配置
    config = Config.load()
    api = APIClient(config)
    auth = AuthManager(config, api)
    cert_mgr = CertManager(config, api)
    payment = PaymentManager(config, api)
    nginx_mgr = NginxManager()
    installer = CertInstaller()

    # ==================== 第1步：认证 ====================
    if not auth.ensure_authenticated():
        console.print("[red]认证失败，程序退出[/red]")
        sys.exit(1)

    # ==================== 第2步：显示金币 ====================
    auth.show_coins()

    # ==================== 第3步：输入域名 ====================
    console.print("\n[bold cyan]请输入需要申请证书的域名：[/bold cyan]")
    console.print("[dim]示例: www.example.com 或 *.example.com[/dim]")

    while True:
        domain_input = Prompt.ask("域名").strip()

        if not domain_input:
            console.print("[red]域名不能为空[/red]")
            continue

        try:
            parsed = cert_mgr.parse_domain_input(domain_input)
            break
        except ValueError as e:
            console.print(f"[red]{e}[/red]")

    domain = parsed['domain']
    prefix = parsed['prefix']
    cert_type = parsed['cert_type']
    full_domain = f"*.{domain}" if cert_type == 'wildcard' else f"{prefix}.{domain}"
    domain_label = full_domain  # 用于显示

    console.print(f"\n[green]证书类型: {'泛域名' if cert_type == 'wildcard' else '单域名'}[/green]")
    console.print(f"[green]域名: {full_domain}[/green]")

    required_coins = SINGLE_CERT_COINS if cert_type == 'single' else WILDCARD_CERT_COINS

    # ==================== 第4步：检查金币 ====================
    while not cert_mgr.check_coins(required_coins):
        console.print(f"\n[red]⚠ 金币不足！需要 {required_coins} 金币[/red]")
        console.print(f"[yellow]当前金币: {api.get_coins()}[/yellow]")

        # 让用户选择充值或退出
        console.print("\n[bold]请选择操作：[/bold]")
        console.print("  1. 去充值")
        console.print("  2. 退出程序")

        choice = Prompt.ask("请选择", choices=["1", "2"], default="1")

        if choice == "2":
            console.print("[yellow]程序退出[/yellow]")
            sys.exit(0)

        # 充值流程
        if not payment.handle_insufficient_coins(required_coins):
            console.print("[yellow]充值取消，程序退出[/yellow]")
            sys.exit(0)

        # 重新检查金币
        current_coins = api.get_coins()
        if current_coins >= required_coins:
            console.print(f"\n[green]✓ 金币已足够！当前金币: {current_coins}[/green]")
            break

    # ==================== 第5步：根据类型走不同流程 ====================
    if cert_type == 'single':
        _handle_single_cert(
            config, api, cert_mgr, nginx_mgr, installer,
            domain, prefix, full_domain
        )
    else:
        _handle_wildcard_cert(
            config, api, cert_mgr, installer,
            domain, full_domain
        )

    console.print("\n[bold green]✓ 证书申请流程完成！[/bold green]")
    console.print("[dim]感谢使用星链下载SSL证书客户端[/dim]")


def _handle_single_cert(
    config: Config,
    api: APIClient,
    cert_mgr: CertManager,
    nginx_mgr: NginxManager,
    installer: CertInstaller,
    domain: str,
    prefix: str,
    full_domain: str,
):
    """处理单域名证书流程（HTTP验证 + Nginx反向代理）"""
    console.print(f"\n[bold cyan]📋 单域名证书申请流程[/bold cyan]")
    console.print(f"[dim]需要域名 {full_domain} 解析到本机才能完成HTTP验证[/dim]")

    # 检查域名解析
    console.print(f"\n[cyan]正在检查域名解析...[/cyan]")
    public_ip = get_public_ip()
    if public_ip:
        console.print(f"[dim]本机公网IP: {public_ip}[/dim]")

    if not check_domain_resolution(full_domain):
        console.print(f"\n[red]⚠ 域名 {full_domain} 未解析到本机[/red]")
        console.print(f"[yellow]请将此客户端安装在域名解析指向的电脑上[/yellow]")
        console.print(f"[yellow]或前往DNS管理后台将域名指向本机IP[/yellow]")

        # 等待用户确认后继续或退出
        choice = Prompt.ask(
            "是否等待域名解析？（等待10秒后自动重试）",
            choices=["y", "n"],
            default="y"
        )
        if choice.lower() != 'y':
            console.print("[yellow]程序退出[/yellow]")
            sys.exit(0)

        # 轮询等待解析
        if not wait_for_domain_resolution(full_domain):
            console.print("[red]域名解析超时，程序退出[/red]")
            sys.exit(1)

    # 配置Nginx反向代理
    console.print(f"\n[cyan]正在配置Nginx反向代理...[/cyan]")
    if not nginx_mgr.setup_acme_proxy(full_domain):
        console.print("[red]Nginx反向代理配置失败[/red]")

        # 如果Nginx不可用，让用户手动配置
        if not nginx_mgr.is_nginx_available():
            console.print(
                "\n[yellow]请手动在Nginx中添加以下配置：[/yellow]"
            )
            console.print(Panel.fit(
                f"server {{\n"
                f"    listen 80;\n"
                f"    server_name {full_domain};\n\n"
                f"    location /.well-known/acme-challenge/ {{\n"
                f"        proxy_pass https://www.cockleshell.cn/.well-known/acme-challenge/;\n"
                f"        proxy_set_header Host www.cockleshell.cn;\n"
                f"    }}\n"
                f"}}",
                title="手动配置"
            ))

            choice = Prompt.ask(
                "配置完成后输入 y 继续，输入 n 退出",
                choices=["y", "n"],
                default="y"
            )
            if choice.lower() != 'y':
                console.print("[yellow]程序退出[/yellow]")
                sys.exit(0)

            # 让用户手动验证
            if not verify_reverse_proxy(full_domain):
                console.print("[red]反向代理验证失败，程序退出[/red]")
                sys.exit(1)
        else:
            sys.exit(1)

    # 申请证书
    task_id = cert_mgr.apply_single_cert(domain, prefix)
    if task_id is None:
        # 清理Nginx配置
        nginx_mgr.cleanup_acme_proxy()
        sys.exit(1)

    # 轮询状态
    result = cert_mgr.poll_task_status(task_id)
    status = result.get('status')

    if status == 'completed':
        # 下载证书
        zip_path = cert_mgr.download_certificate(task_id, full_domain)
        if zip_path:
            # 解压并显示信息
            extract_dir = installer.extract_certificate(zip_path, full_domain)
            if extract_dir:
                installer.print_cert_info(extract_dir, full_domain)
                console.print("[green]证书安装成功！[/green]")
    else:
        error_msg = result.get('error_msg', '未知错误')
        console.print(f"[red]证书申请失败: {error_msg}[/red]")

    # 清理Nginx配置
    console.print(f"\n[cyan]正在清理Nginx配置...[/cyan]")
    nginx_mgr.cleanup_acme_proxy()
    console.print("[green]✓ Nginx配置已清理[/green]")


def _handle_wildcard_cert(
    config: Config,
    api: APIClient,
    cert_mgr: CertManager,
    installer: CertInstaller,
    domain: str,
    full_domain: str,
):
    """处理泛域名证书流程（DNS验证）"""
    console.print(f"\n[bold cyan]📋 泛域名证书申请流程[/bold cyan]")
    console.print("[dim]泛域名证书需要通过DNS验证，支持以下DNS服务商：[/dim]")
    console.print("  1. 阿里云DNS (Aliyun)")
    console.print("  2. 腾讯云DNS (Tencent Cloud)")
    console.print("  3. Cloudflare")

    # 选择DNS服务商
    provider_map = {
        '1': 'aliyun',
        '2': 'tencent',
        '3': 'cloudflare',
    }
    provider_name_map = {
        'aliyun': '阿里云DNS',
        'tencent': '腾讯云DNS',
        'cloudflare': 'Cloudflare',
    }

    while True:
        choice = Prompt.ask(
            "请选择DNS服务商（1/2/3）",
            choices=["1", "2", "3"]
        )
        dns_provider = provider_map.get(choice)
        if dns_provider:
            break

    console.print(f"\n[cyan]DNS服务商: {provider_name_map[dns_provider]}[/cyan]")

    # 获取DNS凭证
    dns_key_id, dns_key_secret = _get_dns_credentials(config, dns_provider)

    # 保存到config.yaml
    config.dns_provider = dns_provider
    if dns_provider == 'aliyun':
        config.aliyun.access_key = dns_key_id
        config.aliyun.access_secret = dns_key_secret
    elif dns_provider == 'tencent':
        config.tencent.secret_id = dns_key_id
        config.tencent.secret_key = dns_key_secret
    elif dns_provider == 'cloudflare':
        config.cloudflare.api_token = dns_key_id  # Cloudflare 用 api_token 代替
        dns_key_secret = ''  # Cloudflare 只有 token
    config.save()
    console.print("[green]✓ DNS凭证已保存到配置文件[/green]")

    # 申请证书
    task_id = cert_mgr.apply_wildcard_cert(
        domain=domain,
        dns_provider=dns_provider,
        dns_key_id=dns_key_id,
        dns_key_secret=dns_key_secret if dns_provider != 'cloudflare' else dns_key_id,
    )
    if task_id is None:
        sys.exit(1)

    # 轮询状态
    result = cert_mgr.poll_task_status(task_id)
    status = result.get('status')

    if status == 'completed':
        # 下载证书
        zip_path = cert_mgr.download_certificate(task_id, full_domain)
        if zip_path:
            # 解压并显示信息
            extract_dir = installer.extract_certificate(zip_path, full_domain)
            if extract_dir:
                installer.print_cert_info(extract_dir, full_domain)
                console.print("[green]证书安装成功！[/green]")
    else:
        error_msg = result.get('error_msg', '未知错误')
        console.print(f"[red]证书申请失败: {error_msg}[/red]")


def _get_dns_credentials(config: Config, provider: str):
    """
    获取DNS服务商凭证
    先检查config.yaml中是否有保存，没有则让用户输入
    """
    key_label_map = {
        'aliyun': ('AccessKey ID', 'AccessKey Secret'),
        'tencent': ('SecretId', 'SecretKey'),
        'cloudflare': ('API Token', ''),  # Cloudflare只有API Token
    }

    labels = key_label_map.get(provider, ('API Key', 'API Secret'))

    # 检查是否已有保存的凭证
    if provider == 'aliyun':
        if config.aliyun.access_key and config.aliyun.access_secret:
            console.print("[dim]检测到已保存的阿里云凭证，是否使用？[/dim]")
            use_saved = Prompt.ask("使用已保存凭证", choices=["y", "n"], default="y")
            if use_saved.lower() == 'y':
                return config.aliyun.access_key, config.aliyun.access_secret

    elif provider == 'tencent':
        if config.tencent.secret_id and config.tencent.secret_key:
            console.print("[dim]检测到已保存的腾讯云凭证，是否使用？[/dim]")
            use_saved = Prompt.ask("使用已保存凭证", choices=["y", "n"], default="y")
            if use_saved.lower() == 'y':
                return config.tencent.secret_id, config.tencent.secret_key

    elif provider == 'cloudflare':
        if config.cloudflare.api_token:
            console.print("[dim]检测到已保存的Cloudflare凭证，是否使用？[/dim]")
            use_saved = Prompt.ask("使用已保存凭证", choices=["y", "n"], default="y")
            if use_saved.lower() == 'y':
                return config.cloudflare.api_token, ''

    # 让用户输入
    console.print(f"\n[bold cyan]请输入{labels[0]}：[/bold cyan]")
    key_id = Prompt.ask(labels[0], password=False)

    if labels[1]:
        console.print(f"[bold cyan]请输入{labels[1]}：[/bold cyan]")
        key_secret = Prompt.ask(labels[1], password=True)
    else:
        key_secret = ''

    return key_id, key_secret


if __name__ == '__main__':
    main()
