#!/usr/bin/env python3
"""
Twitter 登录测试脚本
用于测试 twikit 登录功能和代理配置
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.services.twitter_twikit import TwitterTwikit
from app.config import settings


async def test_login():
    print("=" * 60)
    print("Twitter 登录测试")
    print("=" * 60)
    print(f"代理配置: {settings.proxy_url or '无'}")
    print(f"Twitter 账号: {settings.twitter_username}")
    print(f"Twitter 邮箱: {settings.twitter_email}")
    print("=" * 60)

    if not settings.twitter_username or settings.twitter_username == "your_twitter_username":
        print("\n❌ 错误: Twitter 账号未配置")
        print("请在 .env 文件中配置以下变量:")
        print("  TWITTER_USERNAME=你的Twitter用户名")
        print("  TWITTER_EMAIL=你的Twitter邮箱")
        print("  TWITTER_PASSWORD=你的Twitter密码")
        print("  PROXY_URL=http://127.0.0.1:7896  # 如果需要代理")
        return

    twitter = TwitterTwikit()

    try:
        print("\n开始登录...")
        await twitter.login()
        print("\n✅ 登录成功!")

        print("\n获取用户信息...")
        me = await twitter.get_me()
        print(f"✅ 当前用户: @{me['username']} ({me['name']})")

    except Exception as e:
        print(f"\n❌ 登录失败: {e}")
        print("\n可能的解决方案:")
        print("1. 检查账号密码是否正确")
        print("2. 配置代理: PROXY_URL=http://127.0.0.1:7896")
        print("3. 等待几小时后重试（Twitter 可能临时限制了你的 IP）")
        print("4. 尝试更换代理 IP")


if __name__ == "__main__":
    asyncio.run(test_login())
