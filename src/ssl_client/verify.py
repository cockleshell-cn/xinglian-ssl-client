"""域名解析检测和反向代理验证模块"""

import time
import socket
import requests
from typing import Optional
from rich.console import Console


console = Console()


def get_local_ip() -> str:
    """获取本机公网IP"""
    try:
        # 通过连接外部服务获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        # 不需要真正建立连接
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_public_ip() -> Optional[str]:
    """获取公网IP（通过外部API）"""
    services = [
        'https://api.ipify.org',
        'https://ipv4.icanhazip.com',
        'https://checkip.amazonaws.com',
    ]
    for service in services:
        try:
            resp = requests.get(service, timeout=5)
            if resp.status_code == 200:
                return resp.text.strip()
        except Exception:
            continue
    return None


def check_domain_resolution(domain: str, expected_ip: Optional[str] = None) -> bool:
    """
    检查域名是否解析到本机

    Args:
        domain: 要检查的域名（不含通配符）
        expected_ip: 期望的IP，默认为本机IP

    Returns:
        是否解析到本机
    """
    if expected_ip is None:
        expected_ip = get_public_ip()
        if expected_ip is None:
            expected_ip = get_local_ip()

    try:
        # 获取域名的A记录
        resolved_ip = socket.gethostbyname(domain)
        console.print(f"[dim]域名 {domain} 解析到: {resolved_ip}[/dim]")
        console.print(f"[dim]本机IP: {expected_ip}[/dim]")

        if resolved_ip == expected_ip:
            console.print(f"[green]✓ 域名已解析到本机[/green]")
            return True
        else:
            console.print(
                f"[red]✗ 域名解析到 {resolved_ip}，"
                f"与本机IP ({expected_ip}) 不匹配[/red]"
            )
            return False
    except socket.gaierror as e:
        console.print(f"[red]域名解析失败: {e}[/red]")
        return False


def verify_reverse_proxy(domain: str, timeout: int = 10) -> bool:
    """
    验证反向代理是否生效

    访问 http://{domain}/.well-known/acme-challenge/test 看能否连通

    Args:
        domain: 域名
        timeout: 超时时间

    Returns:
        是否验证成功（能访问到服务器就算成功）
    """
    test_url = f"http://{domain}/.well-known/acme-challenge/test"

    try:
        console.print(f"[dim]验证反向代理: {test_url}[/dim]")
        response = requests.get(test_url, timeout=timeout, allow_redirects=False)

        # 只要服务器响应了就算成功（可能返回404，但说明代理生效了）
        if response.status_code in [200, 301, 302, 404, 403]:
            console.print(f"[green]✓ 反向代理验证成功（HTTP {response.status_code}）[/green]")
            return True
        else:
            console.print(f"[yellow]反向代理响应异常状态码: {response.status_code}[/yellow]")
            return False
    except requests.exceptions.ConnectionError:
        console.print("[red]反向代理验证失败：无法连接到服务器[/red]")
        return False
    except requests.exceptions.Timeout:
        console.print("[red]反向代理验证失败：连接超时[/red]")
        return False
    except Exception as e:
        console.print(f"[red]反向代理验证失败: {e}[/red]")
        return False


def wait_for_domain_resolution(domain: str, max_retries: int = 10, interval: int = 10) -> bool:
    """
    等待域名解析到本机

    Args:
        domain: 域名
        max_retries: 最大重试次数
        interval: 每次重试间隔（秒）

    Returns:
        是否成功
    """
    expected_ip = get_public_ip()
    if expected_ip is None:
        expected_ip = get_local_ip()

    console.print(f"\n[cyan]等待域名 {domain} 解析到 {expected_ip}...[/cyan]")
    console.print(f"[dim]请确保已在DNS管理后台将域名指向本机IP[/dim]")

    for i in range(max_retries):
        try:
            resolved_ip = socket.gethostbyname(domain)
            if resolved_ip == expected_ip:
                console.print(f"[green]✓ 域名已解析到本机[/green]")
                return True

            console.print(
                f"[dim]第{i+1}次检查: 当前解析到 {resolved_ip}，"
                f"期望 {expected_ip} ({interval}秒后重试)[/dim]"
            )
        except socket.gaierror:
            console.print(
                f"[dim]第{i+1}次检查: 域名解析失败 ({interval}秒后重试)[/dim]"
            )

        if i < max_retries - 1:
            time.sleep(interval)

    console.print("[red]域名解析等待超时，请检查DNS配置[/red]")
    return False


def wait_for_proxy(domain: str, max_retries: int = 10, interval: int = 3) -> bool:
    """
    等待反向代理生效

    Args:
        domain: 域名
        max_retries: 最大重试次数
        interval: 每次重试间隔（秒）

    Returns:
        是否成功
    """
    console.print(f"\n[cyan]等待反向代理生效...[/cyan]")

    for i in range(max_retries):
        if verify_reverse_proxy(domain, timeout=5):
            return True

        if i < max_retries - 1:
            console.print(f"[dim]等待 {interval} 秒后重试...[/dim]")
            time.sleep(interval)

    console.print("[red]反向代理等待超时[/red]")
    return False
