# Twitter 登录配置指南

## 快速配置

### 1. 编辑 .env 文件

```bash
cd /home/wwwroot/HAA-Social-Autopilot
vim .env
```

### 2. 填写真实的 Twitter 账号信息

```bash
# 替换为你的真实信息
TWITTER_USERNAME=你的Twitter用户名（如 @your_username，不需要@符号）
TWITTER_EMAIL=你的Twitter邮箱
TWITTER_PASSWORD=你的Twitter密码

# 代理配置（已自动配置）
PROXY_URL=http://host.docker.internal:7896
```

### 3. 重启服务

```bash
docker compose restart backend
```

### 4. 测试登录

访问前端页面测试：
```
http://localhost:3000
进入 Settings 页面 → 点击 "Test Connection"
```

---

## 详细错误提示说明

系统现在会针对每种登录失败情况提供详细的错误提示：

### 错误类型 1: Twitter 服务端临时限制 (错误 399)

**错误信息：**
```
❌ 登录失败: Twitter 服务端临时限制 (错误 399)
```

**原因：**
- IP 地址被标记为可疑
- 登录频率过高
- 账号密码错误导致多次失败
- 缺少有效的代理配置

**解决方案：**
1. 检查代理配置是否正确
2. 更换代理 IP（使用高质量的住宅代理）
3. 等待 2-3 小时后重试
4. 确认账号密码正确
5. 先在浏览器中手动登录一次

---

### 错误类型 2: 账号被锁定 (错误 326)

**错误信息：**
```
❌ 登录失败: 账号被锁定 (错误 326)
```

**原因：**
- Twitter 检测到账号存在异常活动

**解决方案：**
1. 访问 https://x.com 在浏览器中登录
2. 完成 Twitter 要求的验证（手机验证、邮箱验证等）
3. 解锁后等待 1 小时再使用 twikit 登录

---

### 错误类型 3: 请求被拒绝 (错误 403)

**错误信息：**
```
❌ 登录失败: 请求被拒绝 (错误 403)
```

**原因：**
- Cloudflare 或 Twitter 防火墙拦截了请求
- User-Agent 不正确或缺失
- IP 被 Cloudflare 封禁

**解决方案：**
1. 升级 twikit 到最新版本: `pip install -U twikit`
2. 更换代理 IP
3. 检查代理是否能正常访问 https://x.com
4. 确认 twikit 版本 >= 2.3.3

---

### 错误类型 4: 认证失败 (错误 401)

**错误信息：**
```
❌ 登录失败: 认证失败 (错误 401)
```

**原因：**
- 账号密码不正确
- 账号状态异常

**解决方案：**
1. 检查用户名、邮箱、密码是否正确
2. 确认账号未被停用或删除
3. 尝试在浏览器中登录验证账号状态
4. 如果最近修改过密码，请更新 .env 配置

---

### 错误类型 5: 账号密码错误

**错误信息：**
```
❌ 登录失败: 账号密码错误
```

**原因：**
- 提供的用户名、邮箱或密码不正确

**解决方案：**
1. 检查 .env 文件中的配置
2. 确认密码没有特殊字符导致的转义问题
3. 尝试在浏览器中登录验证
4. 如果使用了两步验证，可能需要应用专用密码

---

### 错误类型 6: Cookie 已过期

**错误信息：**
```
❌ 登录失败: Cookie 已过期或无效 (Unauthorized)
```

**原因：**
- 保存的 Cookie 已失效

**解决方案：**
1. 删除旧的 cookie 文件: `rm -f ./data/twitter_cookies.json`
2. 重新登录

---

### 错误类型 7: 网络超时

**错误信息：**
```
❌ 登录失败: 网络超时 (Timeout)
```

**原因：**
- 连接 Twitter 服务器超时
- 网络问题或代理问题

**解决方案：**
1. 检查网络连接是否正常
2. 检查代理服务是否运行（端口 7896）
3. 测试代理: `curl -x http://127.0.0.1:7896 https://x.com`
4. 尝试更换代理服务器

---

### 错误类型 8: 网络连接失败

**错误信息：**
```
❌ 登录失败: 网络连接失败 (Connection Error)
```

**原因：**
- 无法连接到 Twitter 服务器
- 代理配置错误或代理服务未运行
- 防火墙阻止了连接

**解决方案：**
1. 确认代理服务正在运行: `ps aux | grep clash`
2. 测试代理连接: `curl -x http://127.0.0.1:7896 -I https://x.com`
3. 检查 .env 中的 PROXY_URL 配置
4. Docker 容器内使用: `http://host.docker.internal:7896`
5. 宿主机使用: `http://127.0.0.1:7896`

---

### 错误类型 9: 代理错误

**错误信息：**
```
❌ 登录失败: 代理错误 (Proxy Error)
```

**原因：**
- 代理服务器配置错误或无法连接

**解决方案：**
1. 检查代理地址格式: `http://host:port`
2. 确认代理服务正在运行
3. Docker 容器内必须使用: `http://host.docker.internal:7896`
4. 测试代理: `curl -x PROXY_URL -I https://x.com`
5. 如果不需要代理，设置 PROXY_URL 为空

---

### 错误类型 10: 未知错误（错误信息为空）

**错误信息：**
```
❌ 登录失败: 未知错误（错误信息为空）
```

**原因：**
- 网络连接失败（最常见）
- 代理配置错误
- Twitter 服务器无响应

**解决方案：**
1. 配置代理: `PROXY_URL=http://host.docker.internal:7896`
2. 确认代理服务运行: `systemctl status clash`
3. 测试网络: `curl -x http://127.0.0.1:7896 https://x.com`
4. 查看完整日志: `docker compose logs backend -f`

---

## 诊断命令

### 查看实时日志
```bash
cd /home/wwwroot/HAA-Social-Autopilot
docker compose logs backend -f | grep -E "twikit|登录"
```

### 测试代理连接
```bash
# 宿主机测试
curl -x http://127.0.0.1:7896 -I https://x.com

# Docker 容器内测试
docker compose exec backend python -c "
import httpx
proxy = 'http://host.docker.internal:7896'
client = httpx.Client(proxies=proxy, timeout=10)
response = client.head('https://x.com')
print(f'代理连接: HTTP {response.status_code}')
"
```

### 检查配置
```bash
cat .env | grep -E "TWITTER|PROXY"
```

### 删除旧的 Cookie
```bash
rm -f ./data/twitter_cookies.json
```

---

## 常见问题

### Q: 为什么需要代理？
A: 从中国大陆访问 Twitter 需要代理。如果你在海外，可以将 PROXY_URL 设置为空。

### Q: 代理配置正确但仍然失败？
A:
1. 确认 Clash 代理服务正在运行
2. 测试代理能否访问 https://x.com
3. 尝试更换代理节点
4. 检查代理端口是否正确（默认 7896）

### Q: 账号密码正确但登录失败？
A:
1. 先在浏览器中手动登录一次
2. 等待 1-2 小时后再使用 twikit
3. 检查账号是否被锁定或限制
4. 确认没有开启两步验证（或使用应用专用密码）

### Q: 如何查看详细的错误信息？
A:
```bash
docker compose logs backend --tail 100 | grep -A 20 "登录失败"
```

---

## 技术支持

如果以上方案都无法解决问题：

1. 查看完整日志并截图错误信息
2. 检查 twikit 版本: `docker compose exec backend pip show twikit`
3. 提交 issue 到项目仓库，附上：
   - 错误日志
   - 配置信息（隐藏敏感信息）
   - twikit 版本
   - 是否使用代理

---

**最后更新:** 2026-03-10
**状态:** ✅ 代理已配置，错误提示已增强
