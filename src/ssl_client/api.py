"""API客户端模块 - 对接星链下载后端API"""

import time
import requests
from typing import Optional, Dict, Any
from .config import Config


class APIClient:
    """星链下载API客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.api_base.rstrip('/')
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self):
        """更新请求头"""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        if self.config.token:
            self.session.headers['Authorization'] = f'Bearer {self.config.token}'

    def set_token(self, token: str):
        """设置token"""
        self.config.token = token
        self._update_headers()

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.base_url}{endpoint}"

        # 添加请求间隔，避免触发限流
        time.sleep(0.5)

        response = self.session.request(method, url, **kwargs)

        if response.status_code == 401:
            raise AuthenticationError("认证失败，请重新登录")

        if response.status_code == 402:
            raise InsufficientCoinsError("金币不足")

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', response.text)
            except:
                error_msg = response.text
            raise APIError(f"API错误: {error_msg}")

        return response.json()

    def _request_raw(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """发送请求并返回原始响应（用于下载等场景）"""
        url = f"{self.base_url}{endpoint}"
        time.sleep(0.5)
        response = self.session.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise APIError(f"请求失败: {response.status_code}")
        return response

    # ==================== 认证相关 ====================

    def send_sms_code(self, phone: str) -> Dict[str, Any]:
        """发送短信验证码"""
        return self._request('POST', '/auth/send-code', json={'phone': phone})

    def login_or_register(self, phone: str, code: str) -> Dict[str, Any]:
        """
        短信验证码登录/注册一体
        返回: {token, api_token, is_new_user, user:{id,phone,coins,role}}
        """
        return self._request('POST', '/auth/sms-login', json={
            'phone': phone,
            'code': code,
        })

    # ==================== 用户相关 ====================

    def verify_api_token(self, api_token: str) -> Dict[str, Any]:
        """通过api_token验证用户身份，获取用户信息"""
        return self._request('GET', f'/auth/verify-api-token', params={'api_token': api_token})

    def get_coins(self) -> int:
        """获取剩余金币数"""
        try:
            data = self.verify_api_token(self.config.api_token)
            return data.get('coins', 0)
        except Exception:
            return 0

    # ==================== SSL证书相关 ====================

    def apply_certificate(
        self,
        domain: str,
        cert_type: str = 'single',
        verify_method: str = 'http',
        prefix: str = 'www',
        dns_provider: Optional[str] = None,
        dns_key_id: Optional[str] = None,
        dns_key_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        申请SSL证书

        Args:
            domain: 根域名 (e.g. example.com)
            cert_type: 证书类型 single/wildcard
            verify_method: 验证方式 http/dns
            prefix: 前缀 (单域名如 www, 泛域名 *)
            dns_provider: DNS服务商 aliyun/tencent/cloudflare
            dns_key_id: DNS API密钥ID
            dns_key_secret: DNS API密钥Secret
        """
        payload = {
            'domain': domain,
            'cert_type': cert_type,
            'verify_method': verify_method,
            'prefix': prefix,
        }

        if verify_method == 'dns' and dns_provider:
            payload['dns_provider'] = dns_provider
            payload['dns_key_id'] = dns_key_id or ''
            payload['dns_key_secret'] = dns_key_secret or ''

        return self._request('POST', '/ssl/apply', json=payload, params={'api_token': self.config.api_token})

    def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """获取任务状态"""
        return self._request('GET', f'/ssl/status/{task_id}', params={'api_token': self.config.api_token})

    def download_certificate(self, task_id: int, save_path: str) -> str:
        """下载证书到指定路径，返回文件路径"""
        # Step 1: 获取下载链接（返回JSON包含download_url）
        response = self._request(
            'GET',
            f'/ssl/download/{task_id}',
            params={'api_token': self.config.api_token}
        )
        download_url = response.get('download_url')
        if not download_url:
            raise APIError(500, "服务器未返回下载链接")

        # Step 2: 使用完整URL下载真实的zip文件
        full_url = self.base_url.replace('/api', '') + download_url
        file_response = self.session.request('GET', full_url)
        if file_response.status_code >= 400:
            raise APIError(f"下载失败: {file_response.status_code}")
        with open(save_path, 'wb') as f:
            f.write(file_response.content)
        return save_path

    # ==================== 支付相关 ====================

    def get_packages(self) -> Dict[str, Any]:
        """获取充值套餐"""
        return self._request('GET', '/payment/packages', params={'api_token': self.config.api_token})

    def create_order(self, package_id: int) -> Dict[str, Any]:
        """
        创建充值订单
        返回: {order_no, amount, coins, pay_url}
        """
        return self._request(
            'POST', '/payment/create',
            json={'package_id': package_id},
            params={'api_token': self.config.api_token}
        )

    def get_order_status(self, order_no: str) -> Dict[str, Any]:
        """查询订单状态"""
        return self._request(
            'GET', f'/payment/status/{order_no}',
            params={'api_token': self.config.api_token}
        )

    def get_recharge_url(self) -> str:
        """获取充值页面URL"""
        return self.config.api_base.replace('/api', '/recharge')


class APIError(Exception):
    """API错误"""
    pass


class AuthenticationError(APIError):
    """认证错误"""
    pass


class InsufficientCoinsError(APIError):
    """金币不足错误"""
    pass
