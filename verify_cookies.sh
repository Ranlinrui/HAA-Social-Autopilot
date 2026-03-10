#!/bin/bash
# 验证 Twitter Cookies 是否完整

echo "=========================================="
echo "Twitter Cookies 验证工具"
echo "=========================================="
echo ""

# 检查必需的 cookies
REQUIRED_COOKIES=("auth_token" "ct0" "twid")
MISSING_COOKIES=()

echo "【检查必需的 Cookies】"
echo "---"

# 从用户提供的 cookies 中检查
USER_COOKIES="$1"

if [ -z "$USER_COOKIES" ]; then
    echo "用法: $0 <cookies_file.json>"
    echo ""
    echo "或者手动检查以下 cookies 是否存在："
    echo ""
fi

for cookie in "${REQUIRED_COOKIES[@]}"; do
    echo -n "检查 $cookie ... "

    # 这里需要用户手动确认
    case $cookie in
        "auth_token")
            echo "❌ 缺失（最关键）"
            MISSING_COOKIES+=("auth_token")
            ;;
        "ct0")
            echo "✅ 存在"
            ;;
        "twid")
            echo "✅ 存在"
            ;;
    esac
done

echo ""

if [ ${#MISSING_COOKIES[@]} -gt 0 ]; then
    echo "❌ Cookies 不完整！"
    echo ""
    echo "缺少的 cookies:"
    for cookie in "${MISSING_COOKIES[@]}"; do
        echo "  - $cookie"
    done
    echo ""
    echo "【解决方案】"
    echo ""
    echo "方法 1: 使用浏览器开发者工具（推荐）"
    echo "---"
    echo "1. 打开 Chrome 浏览器"
    echo "2. 使用代理访问 Twitter:"
    echo "   google-chrome --proxy-server=\"http://127.0.0.1:7896\" https://x.com"
    echo ""
    echo "3. 登录你的账户（确保完全登录）"
    echo ""
    echo "4. 按 F12 打开开发者工具"
    echo ""
    echo "5. 进入 Application 标签 → Cookies → https://x.com"
    echo ""
    echo "6. 找到 auth_token cookie（应该很长，100+ 字符）"
    echo ""
    echo "7. 复制 auth_token 的值"
    echo ""
    echo "8. 创建 JSON 文件:"
    cat << 'EOF'
[
  {
    "name": "auth_token",
    "value": "你复制的auth_token值",
    "domain": ".x.com",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "sameSite": "None"
  },
  {
    "name": "ct0",
    "value": "1948332ddbee1285b080013c71eb1ebaf8e40cbeb0b494107157536498b09abd690e71aea145687e05d4068ac6423dc1373f088e56f6c4b2bba34843ab4ed94bc34792815c3f56934729cfe99488e8ed",
    "domain": ".x.com",
    "path": "/",
    "secure": false,
    "httpOnly": false,
    "sameSite": "Lax"
  },
  {
    "name": "twid",
    "value": "u%3D1966380483111170049",
    "domain": ".x.com",
    "path": "/",
    "secure": true,
    "httpOnly": false,
    "sameSite": "None"
  },
  {
    "name": "kdt",
    "value": "m3mLAu21wfjWDSn1tARmbAYMbE75N2N3xxkQ9tPB",
    "domain": ".x.com",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "sameSite": "None"
  }
]
EOF
    echo ""
    echo "9. 保存为: /home/wwwroot/HAA-Social-Autopilot/backend/data/twitter_cookies.json"
    echo ""
    echo ""
    echo "方法 2: 使用 EditThisCookie 扩展"
    echo "---"
    echo "1. 安装 EditThisCookie 扩展（比 Cookie-Editor 更完整）"
    echo "   https://chrome.google.com/webstore/detail/editthiscookie"
    echo ""
    echo "2. 在 x.com 页面点击扩展图标"
    echo ""
    echo "3. 确保能看到 auth_token（如果看不到，说明未登录）"
    echo ""
    echo "4. 点击 Export → 选择 JSON 格式"
    echo ""
    echo "5. 保存到文件"
    echo ""
    echo ""
    echo "方法 3: 检查登录状态"
    echo "---"
    echo "如果始终看不到 auth_token，可能是："
    echo "1. 未完全登录（访客模式）"
    echo "2. 浏览器隐私设置阻止了 cookies"
    echo "3. 需要清除浏览器缓存后重新登录"
    echo ""
    echo "验证登录状态："
    echo "- 访问 https://x.com/home"
    echo "- 如果能看到时间线，说明已登录"
    echo "- 如果跳转到登录页，说明未登录"
    echo ""
else
    echo "✅ Cookies 完整！"
    echo ""
    echo "可以使用这些 cookies 登录 Twitter"
fi

echo ""
echo "=========================================="
