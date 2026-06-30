# 公网访问与登录验证

本系统支持通过 **HTTPS 反向代理 + JWT 登录** 安全暴露 Web 控制台。

> **警告**：控制台包含 Kill Switch、紧急全平、策略修改等敏感操作。**未启用登录验证时，切勿将服务暴露到公网。**

## 1. 启用登录验证

编辑 `.env`：

```bash
# 开启 Web 登录（本地开发可保持 false）
WEB_AUTH_ENABLED=true
WEB_AUTH_USERNAME=你的用户名
WEB_AUTH_PASSWORD=你的强密码
# 随机长字符串，可用: openssl rand -hex 32
WEB_AUTH_SECRET=请替换为随机密钥
WEB_AUTH_TOKEN_HOURS=24

# 公网域名（CORS，多个用逗号分隔）
WEB_ALLOWED_ORIGINS=https://your-domain.com
```

重启 Web 服务：

```bash
bash scripts/start_web.sh
```

浏览器访问时会跳转到 `/login` 登录页。

### 1.1 多用户注册（推荐公网使用）

默认开放注册（`WEB_ALLOW_REGISTER=true`）。流程：

1. 打开 `/register` 注册账号
2. 登录后进入 **交易所连接**，填写并保存 OKX API Key（加密存入服务器，仅属于该账号）
3. 在 **持仓复盘 / 持仓分析 / 仪表盘** 查看自己的数据

每个注册用户的数据与 API Key 相互隔离；`.env` 中的管理员账号仍可用于本机运维（使用环境变量密钥）。

关闭注册：

```bash
WEB_ALLOW_REGISTER=false
WEB_AUTH_USERNAME=管理员用户名
WEB_AUTH_PASSWORD=管理员密码
```

## 2. 公网 HTTPS（推荐 Caddy）

### 2.1 防火墙

只开放 **80 / 443**，不要对外开放 **8000**：

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2.2 启动本机 Web（仅监听本机或内网）

`scripts/start_web.sh` 默认绑定 `0.0.0.0:8000`。有反向代理时，可在防火墙层禁止公网访问 8000。

### 2.3 Caddy 反向代理

1. 将域名 DNS A 记录指向 VPS 公网 IP
2. 编辑 `deploy/Caddyfile`，把 `your-domain.com` 改成你的域名
3. 启动：

```bash
sudo caddy run --config deploy/Caddyfile
```

Caddy 会自动配置 HTTPS 证书。

### 2.4 其他方式

- **Nginx + Certbot**：同样反代到 `127.0.0.1:8000`
- **Cloudflare Tunnel**：无需开放端口，适合无公网 IP 的场景；需在 Cloudflare 侧配置 Access 或仍启用本系统 JWT

## 3. 安全建议

1. 使用 **强密码** 和 **随机 WEB_AUTH_SECRET**
2. OKX API Key 权限仅勾选「读取 + 交易」，**禁用提币**
3. 定期更新系统与依赖
4. 考虑 IP 白名单（云厂商安全组 / ufw）作为额外一层
5. 实盘前完成 `docs/LIVE_SAFETY_CHECKLIST.md`

## 4. 本地开发

不设置 `WEB_AUTH_ENABLED`（或设为 `false`）时，与之前一样无需登录，适合本机调试。
