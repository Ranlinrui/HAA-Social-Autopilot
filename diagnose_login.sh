#!/bin/bash
# HAA Social Autopilot - Twitter Login Diagnostic Script
# 诊断 twikit 模式下 Twitter 登录失败的原因

echo "=========================================="
echo "HAA Social Autopilot - Twitter 登录诊断"
echo "=========================================="
echo ""

# 1. 检查 .env 配置
echo "【1】检查 .env 配置"
echo "---"
cd /home/wwwroot/HAA-Social-Autopilot

if [ ! -f .env ]; then
    echo "❌ .env 文件不存在"
    exit 1
fi

echo "Twitter 账号配置:"
TWITTER_USERNAME=$(grep "^TWITTER_USERNAME=" .env | cut -d'=' -f2)
TWITTER_EMAIL=$(grep "^TWITTER_EMAIL=" .env | cut -d'=' -f2)
TWITTER_PASSWORD=$(grep "^TWITTER_PASSWORD=" .env | cut -d'=' -f2)
PROXY_URL=$(grep "^PROXY_URL=" .env | cut -d'=' -f2)

echo "  用户名: $TWITTER_USERNAME"
echo "  邮箱: $TWITTER_EMAIL"
echo "  密码: ${TWITTER_PASSWORD:0:3}***"
echo "  代理: $PROXY_URL"
echo ""

# 检查是否为占位符
if [ "$TWITTER_USERNAME" = "your_twitter_username" ] || [ -z "$TWITTER_USERNAME" ]; then
    echo "❌ 问题 1: Twitter 用户名未配置（仍为占位符）"
    echo "   解决方案: 编辑 .env 文件，填写真实的 Twitter 用户名"
    echo ""
fi

if [ "$TWITTER_EMAIL" = "your_twitter_email" ] || [ -z "$TWITTER_EMAIL" ]; then
    echo "❌ 问题 2: Twitter 邮箱未配置（仍为占位符）"
    echo "   解决方案: 编辑 .env 文件，填写真实的 Twitter 邮箱"
    echo ""
fi

if [ "$TWITTER_PASSWORD" = "your_twitter_password" ] || [ -z "$TWITTER_PASSWORD" ]; then
    echo "❌ 问题 3: Twitter 密码未配置（仍为占位符）"
    echo "   解决方案: 编辑 .env 文件，填写真实的 Twitter 密码"
    echo ""
fi

# 2. 检查代理配置
echo "【2】检查代理配置"
echo "---"

if [ -z "$PROXY_URL" ]; then
    echo "⚠️  警告: 代理未配置（中国大陆访问 Twitter 需要代理）"
    echo "   解决方案: 设置 PROXY_URL=http://host.docker.internal:7896"
    echo ""
else
    echo "✅ 代理已配置: $PROXY_URL"
    echo ""
fi

# 3. 检查代理服务是否运行
echo "【3】检查代理服务状态"
echo "---"

if ps aux | grep -v grep | grep -q "clash\|v2ray\|xray"; then
    echo "✅ 代理服务正在运行"
    ps aux | grep -v grep | grep -E "clash|v2ray|xray" | head -3
else
    echo "❌ 问题 4: 代理服务未运行"
    echo "   解决方案: 启动 Clash 或其他代理服务"
fi
echo ""

# 4. 测试代理连接
echo "【4】测试代理连接"
echo "---"

if [ -n "$PROXY_URL" ]; then
    echo "测试代理访问 Twitter..."
    if timeout 10 curl -x "$PROXY_URL" -I https://x.com 2>&1 | grep -q "HTTP/"; then
        echo "✅ 代理可以访问 Twitter"
        curl -x "$PROXY_URL" -I https://x.com 2>&1 | head -1
    else
        echo "❌ 问题 5: 代理无法访问 Twitter"
        echo "   可能原因:"
        echo "   - 代理服务未运行"
        echo "   - 代理端口错误"
        echo "   - 代理节点失效"
        echo "   解决方案: 检查代理服务并更换节点"
    fi
else
    echo "⚠️  跳过（代理未配置）"
fi
echo ""

# 5. 检查 Docker 容器状态
echo "【5】检查 Docker 容器状态"
echo "---"

if docker ps | grep -q "haa-social-autopilot_backend"; then
    echo "✅ 后端容器正在运行"
    docker ps | grep "haa-social-autopilot_backend"
else
    echo "❌ 问题 6: 后端容器未运行"
    echo "   解决方案: docker compose up -d"
fi
echo ""

# 6. 检查容器内代理连接
echo "【6】检查容器内代理连接"
echo "---"

if docker ps | grep -q "haa-social-autopilot_backend"; then
    echo "测试容器内访问 Twitter..."
    docker compose exec -T backend python -c "
import httpx
import sys

proxy = 'http://host.docker.internal:7896'
try:
    client = httpx.Client(proxies=proxy, timeout=10)
    response = client.head('https://x.com')
    print(f'✅ 容器内代理连接成功: HTTP {response.status_code}')
    sys.exit(0)
except Exception as e:
    print(f'❌ 问题 7: 容器内代理连接失败')
    print(f'   错误: {type(e).__name__}: {e}')
    print(f'   解决方案: 检查 Docker 网络配置')
    sys.exit(1)
" 2>&1
else
    echo "⚠️  跳过（容器未运行）"
fi
echo ""

# 7. 查看最近的登录日志
echo "【7】查看最近的登录日志"
echo "---"

if docker ps | grep -q "haa-social-autopilot_backend"; then
    echo "最近 20 条 twikit 相关日志:"
    docker logs haa-social-autopilot_backend_1 2>&1 | grep -E "twikit|登录" | tail -20
else
    echo "⚠️  跳过（容器未运行）"
fi
echo ""

# 8. 检查 twikit 版本
echo "【8】检查 twikit 版本"
echo "---"

if docker ps | grep -q "haa-social-autopilot_backend"; then
    docker compose exec -T backend pip show twikit 2>&1 | grep -E "Name|Version"
else
    echo "⚠️  跳过（容器未运行）"
fi
echo ""

# 9. 总结
echo "=========================================="
echo "诊断总结"
echo "=========================================="
echo ""

ISSUES=0

if [ "$TWITTER_USERNAME" = "your_twitter_username" ] || [ -z "$TWITTER_USERNAME" ]; then
    echo "❌ Twitter 用户名未配置"
    ISSUES=$((ISSUES+1))
fi

if [ "$TWITTER_EMAIL" = "your_twitter_email" ] || [ -z "$TWITTER_EMAIL" ]; then
    echo "❌ Twitter 邮箱未配置"
    ISSUES=$((ISSUES+1))
fi

if [ "$TWITTER_PASSWORD" = "your_twitter_password" ] || [ -z "$TWITTER_PASSWORD" ]; then
    echo "❌ Twitter 密码未配置"
    ISSUES=$((ISSUES+1))
fi

if [ -z "$PROXY_URL" ]; then
    echo "⚠️  代理未配置（中国大陆必需）"
fi

if ! ps aux | grep -v grep | grep -q "clash\|v2ray\|xray"; then
    echo "❌ 代理服务未运行"
    ISSUES=$((ISSUES+1))
fi

echo ""

if [ $ISSUES -eq 0 ]; then
    echo "✅ 所有检查通过"
    echo ""
    echo "如果仍然无法登录，请:"
    echo "1. 查看完整日志: docker compose logs backend -f"
    echo "2. 尝试在浏览器中手动登录 https://x.com"
    echo "3. 等待 1-2 小时后重试（可能是 Twitter 临时限制）"
else
    echo "⚠️  发现 $ISSUES 个问题，请按照上述提示修复"
    echo ""
    echo "快速修复步骤:"
    echo "1. 编辑配置: vim /home/wwwroot/HAA-Social-Autopilot/.env"
    echo "2. 填写真实的 Twitter 账号信息"
    echo "3. 确认代理服务运行: systemctl status clash"
    echo "4. 重启服务: docker compose restart backend"
    echo "5. 测试登录: 访问 http://localhost:3000 → Settings → Test Connection"
fi

echo ""
echo "=========================================="
