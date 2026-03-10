#!/usr/bin/env python3
"""
Twitter 交互式登录脚本
支持在终端中登录 Twitter，处理验证码等交互
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from twikit import Client
from twikit.errors import BadRequest


async def interactive_login(username=None, email=None, password=None, proxy=None, auto_mode=False):
    print("=" * 60)
    print("Twitter 交互式登录")
    print("=" * 60)

    # 如果是自动模式（传入了参数），不进行交互
    if not auto_mode:
        # 如果没有传入参数，则交互式获取
        if not username:
            username = input("请输入 Twitter 用户名 (如 @LinRui0203): ").strip()
        if not email:
            email = input("请输入 Twitter 邮箱: ").strip()
        if not password:
            password = input("请输入 Twitter 密码: ").strip()

        # 如果没有指定代理，询问
        if proxy is None:
            use_proxy = input("是否使用代理? (y/n, 默认 n): ").strip().lower()
            if use_proxy == 'y':
                proxy = input("请输入代理地址 (如 http://127.0.0.1:7896): ").strip()

    print("\n" + "=" * 60)
    print(f"用户名: {username}")
    print(f"邮箱: {email}")
    print(f"代理: {proxy or '不使用'}")
    print("=" * 60)

    # 创建客户端
    print("\n创建 twikit 客户端...")
    client = Client(language='en-US', proxy=proxy)

    # 设置请求头
    client.http.headers.update({
        'User-Agent': client._user_agent,
        'Referer': 'https://x.com/',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    cookies_file = "./data/twitter_cookies.json"

    try:
        print("\n开始登录...")
        print("(如果需要验证码，会提示你输入)")

        # 尝试登录
        result = await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
            cookies_file=cookies_file,
            enable_ui_metrics=True
        )

        print("\n✅ 登录成功!")
        print(f"登录结果: {result}")

        # 保存 cookies
        client.save_cookies(cookies_file)
        print(f"✅ Cookies 已保存到: {cookies_file}")

        # 获取用户信息
        print("\n获取用户信息...")
        me = await client.user()
        print(f"✅ 当前用户: @{me.screen_name} ({me.name})")
        print(f"   粉丝数: {me.followers_count}")
        print(f"   关注数: {me.following_count}")

    except BadRequest as e:
        error_msg = str(e)
        print(f"\n❌ 登录失败: {error_msg}")

        if "399" in error_msg or "Could not log you in now" in error_msg:
            print("\n这是 Twitter 的临时限制 (错误 399)")
            print("\n可能的解决方案:")
            print("1. 等待 2-3 小时后重试")
            print("2. 更换代理 IP")
            print("3. 先在浏览器中手动登录一次")
            print("4. 检查账号密码是否正确")
        elif "326" in error_msg:
            print("\n账号被锁定，需要完成验证")
            print("请访问 https://x.com 在浏览器中解锁账号")
        else:
            print("\n未知错误，请检查账号信息是否正确")

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    # 支持命令行参数
    if len(sys.argv) >= 4:
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
        proxy = sys.argv[4] if len(sys.argv) > 4 else None
        asyncio.run(interactive_login(username, email, password, proxy, auto_mode=True))
    else:
        asyncio.run(interactive_login())
