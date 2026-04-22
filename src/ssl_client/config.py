"""配置管理模块"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class AliyunConfig:
    """阿里云DNS配置"""
    access_key: str = ""
    access_secret: str = ""


@dataclass
class TencentConfig:
    """腾讯云DNS配置"""
    secret_id: str = ""
    secret_key: str = ""


@dataclass
class CloudflareConfig:
    """Cloudflare DNS配置"""
    api_token: str = ""


@dataclass
class Config:
    """客户端配置"""
    # API Token（主要认证方式，与JWT token不同）
    api_token: str = ""
    # JWT Token（仅用于部分接口的Bearer认证，可选）
    jwt_token: str = ""

    api_base: str = "https://www.cockleshell.cn/api"
    dns_provider: str = ""  # aliyun, tencent, cloudflare
    aliyun: AliyunConfig = field(default_factory=AliyunConfig)
    tencent: TencentConfig = field(default_factory=TencentConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)

    # 兼容旧字段名
    @property
    def token(self) -> str:
        return self.api_token

    @token.setter
    def token(self, value: str):
        self.api_token = value

    @classmethod
    def get_config_dir(cls) -> Path:
        """获取配置目录"""
        if os.name == 'nt':  # Windows
            base = Path(os.environ.get('APPDATA', '~'))
        else:  # Linux/macOS
            base = Path.home()
        return base / '.xinglian-ssl'

    @classmethod
    def get_config_file(cls) -> Path:
        """获取配置文件路径"""
        return cls.get_config_dir() / 'config.yaml'

    def ensure_config_dir(self):
        """确保配置目录存在"""
        config_dir = self.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)

    def save(self):
        """保存配置到文件"""
        self.ensure_config_dir()
        config_file = self.get_config_file()

        data = {
            'api_token': self.api_token,
            'api_base': self.api_base,
            'dns_provider': self.dns_provider,
            'aliyun': {
                'access_key': self.aliyun.access_key,
                'access_secret': self.aliyun.access_secret,
            },
            'tencent': {
                'secret_id': self.tencent.secret_id,
                'secret_key': self.tencent.secret_key,
            },
            'cloudflare': {
                'api_token': self.cloudflare.api_token,
            },
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls) -> 'Config':
        """从文件加载配置"""
        config_file = cls.get_config_file()

        if not config_file.exists():
            return cls()

        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        config = cls()
        # 兼容旧字段名 token -> api_token
        config.api_token = data.get('api_token', data.get('token', ''))
        config.api_base = data.get('api_base', 'https://www.cockleshell.cn/api')
        config.dns_provider = data.get('dns_provider', '')

        if 'aliyun' in data:
            config.aliyun = AliyunConfig(
                access_key=data['aliyun'].get('access_key', ''),
                access_secret=data['aliyun'].get('access_secret', ''),
            )

        if 'tencent' in data:
            config.tencent = TencentConfig(
                secret_id=data['tencent'].get('secret_id', ''),
                secret_key=data['tencent'].get('secret_key', ''),
            )

        if 'cloudflare' in data:
            config.cloudflare = CloudflareConfig(
                api_token=data['cloudflare'].get('api_token', ''),
            )

        return config

    def has_api_token(self) -> bool:
        """检查是否已配置api_token"""
        return bool(self.api_token)

    def get_dns_credentials(self) -> Optional[Dict[str, Any]]:
        """获取DNS服务商凭证"""
        if self.dns_provider == 'aliyun':
            if self.aliyun.access_key and self.aliyun.access_secret:
                return {
                    'provider': 'aliyun',
                    'access_key': self.aliyun.access_key,
                    'access_secret': self.aliyun.access_secret,
                }
        elif self.dns_provider == 'tencent':
            if self.tencent.secret_id and self.tencent.secret_key:
                return {
                    'provider': 'tencent',
                    'secret_id': self.tencent.secret_id,
                    'secret_key': self.tencent.secret_key,
                }
        elif self.dns_provider == 'cloudflare':
            if self.cloudflare.api_token:
                return {
                    'provider': 'cloudflare',
                    'api_token': self.cloudflare.api_token,
                }
        return None
