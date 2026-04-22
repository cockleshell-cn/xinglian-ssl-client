# 星链下载SSL证书客户端

自动申请和安装SSL证书的命令行工具，支持 Windows、Linux 和 macOS。

## 功能特性

- 🚀 自动申请免费SSL证书（Let's Encrypt）
- 🔒 支持单域名（100金币）和泛域名（200金币）证书
- 📱 手机号+验证码登录/注册，自动保存api_token
- 💰 内置金币充值和余额检测
- 🌐 单域名：自动配置Nginx反向代理进行HTTP验证
- ☁️ 泛域名：支持阿里云DNS/腾讯云DNS/Cloudflare验证
- 🔄 自动轮询申请状态并下载证书
- 🧹 申请完成后自动清理Nginx临时配置

## 安装

### 从源码运行

```bash
# 克隆项目
git clone https://github.com/cockleshell/xinglian-ssl-client.git
cd xinglian-ssl-client

# 安装依赖
pip install -e .

# 运行
xinglian-ssl
```

### Windows

下载 `xinglian-ssl-client-windows.exe`，双击运行。

### Linux/macOS

```bash
chmod +x xinglian-ssl-client
./xinglian-ssl-client
```

## 使用方法

### 完整流程

```bash
xinglian-ssl
```

首次运行会引导您：
1. **登录/注册** — 输入手机号，获取验证码，自动登录或注册
2. **输入域名** — 支持 `www.example.com` 或 `*.example.com`
3. **检查金币** — 如果金币不足，自动引导充值
4. **单域名流程** — 检查域名解析 → 配置Nginx → 申请证书 → 下载安装 → 清理配置
5. **泛域名流程** — 输入DNS凭证 → 提交申请 → 轮询状态 → 下载安装

### 配置DNS凭证（泛域名证书使用）

DNS凭证会保存在 `~/.xinglian-ssl/config.yaml` 中，下次使用可复用：

```yaml
api_token: "your-api-token"
dns_provider: "aliyun"  # aliyun, tencent, cloudflare
aliyun:
  access_key: "your-access-key"
  access_secret: "your-access-secret"
tencent:
  secret_id: "your-secret-id"
  secret_key: "your-secret-key"
cloudflare:
  api_token: "your-api-token"
```

## 证书类型

| 类型 | 金币消耗 | 验证方式 | 适用场景 |
|------|---------|---------|---------|
| 单域名 | 100 | HTTP验证（需Nginx） | 已有服务器的域名 |
| 泛域名 | 200 | DNS验证 | 有DNS管理权限的域名 |

## 目录结构

```
ssl-client/
├── src/ssl_client/
│   ├── __init__.py    # 包入口
│   ├── main.py        # 主流程（CLI交互）
│   ├── api.py         # API客户端（请求后端）
│   ├── auth.py        # 用户认证（手机号+验证码）
│   ├── config.py      # 配置管理（config.yaml）
│   ├── cert.py        # 证书申请和管理
│   ├── payment.py     # 支付/充值模块
│   ├── nginx.py       # Nginx配置管理
│   ├── verify.py      # 域名解析检测和反向代理验证
│   ├── installer.py   # 证书安装
│   └── dns.py         # DNS验证（备选）
├── pyproject.toml
└── README.md
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 打包为可执行文件
pyinstaller --onefile src/ssl_client/main.py
```

## 许可证

MIT License
