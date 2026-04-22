"""域名解析检测模块"""

import socket
import time
import dns.resolver
from typing import Optional, Tuple
from rich.console import Console
from rich.prompt import Prompt


console = Console()


class DNSChecker:
    """域名解析检测器"""
    
    def __init__(self):
        self.local_ip = self._get_local_ip()
    
    def _get_local_ip(self) -> str:
        """获取本机公网IP"""
        try:
            # 尝试通过DNS查询获取
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def get_domain_ip(self, domain: str) -> Optional[str]:
        """获取域名解析的IP地址"""
        try:
            # 使用dnspython解析
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(domain, 'A')
            if answers:
                return str(answers[0])
        except dns.resolver.NXDOMAIN:
            console.print(f"[red]域名 {domain} 不存在[/red]")
        except dns.resolver.NoAnswer:
            console.print(f"[red]域名 {domain} 没有A记录[/red]")
        except dns.resolver.Timeout:
            console.print(f"[red]解析域名 {domain} 超时[/red]")
        except Exception as e:
            console.print(f"[red]解析域名 {domain} 失败: {e}[/red]")
        
        return None
    
    def is_resolved_to_local(self, domain: str) -> bool:
        """检查域名是否解析到本机"""
        domain_ip = self.get_domain_ip(domain)
        if domain_ip is None:
            return False
        
        console.print(f"[dim]域名 {domain} 解析到: {domain_ip}[/dim]")
        console.print(f"[dim]本机IP: {self.local_ip}[/dim]")
        
        return domain_ip == self.local_ip
    
    def check_domain_resolution(self, domain: str) -> Tuple[bool, str]:
        """
        检查域名解析状态
        
        Returns:
            (是否解析到本机, 提示信息)
        """
        console.print(f"\n[cyan]检查域名解析...[/cyan]")
        
        domain_ip = self.get_domain_ip(domain)
        if domain_ip is None:
            return False, f"域名 {domain} 无法解析，请先添加DNS解析记录"
        
        if domain_ip == self.local_ip:
            console.print(f"[green]✓ 域名 {domain} 已解析到本机 ({self.local_ip})[/green]")
            return True, f"域名已正确解析到本机"
        else:
            console.print(f"[yellow]⚠ 域名 {domain} 解析到 {domain_ip}，但本机IP是 {self.local_ip}[/yellow]")
            return False, f"域名解析到 {domain_ip}，需要将客户端安装在域名指向的服务器上，或将域名解析修改为指向本机 ({self.local_ip})"
    
    def wait_for_resolution(self, domain: str, max_wait: int = 300) -> bool:
        """等待域名解析生效"""
        console.print(f"[dim]等待域名解析生效...[/dim]")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self.is_resolved_to_local(domain):
                return True
            console.print("[dim]解析未生效，30秒后重试...[/dim]")
            time.sleep(30)
        
        return False


def parse_domain_input(domain_input: str) -> Tuple[str, str, bool]:
    """
    解析用户输入的域名
    
    Args:
        domain_input: 用户输入，如 www.example.com, test.example.com, *.example.com
    
    Returns:
        (完整域名, 主域名, 是否泛域名)
    """
    domain_input = domain_input.strip().lower()
    
    # 检查是否是泛域名
    if domain_input.startswith('*'):
        is_wildcard = True
        # *.example.com -> example.com
        main_domain = domain_input[2:]  # 去掉 "*."
        return domain_input, main_domain, is_wildcard
    else:
        is_wildcard = False
        # www.example.com -> example.com
        parts = domain_input.split('.')
        if len(parts) >= 2:
            main_domain = '.'.join(parts[-2:])
        else:
            main_domain = domain_input
        return domain_input, main_domain, is_wildcard


def get_domain_type_info(is_wildcard: bool) -> Tuple[str, int]:
    """
    获取域名类型信息
    
    Returns:
        (类型名称, 所需金币)
    """
    if is_wildcard:
        return "泛域名证书", 200
    else:
        return "单域名证书", 100