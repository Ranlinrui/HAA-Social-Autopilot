from typing import Optional, List
import os
import asyncio
import mimetypes
import httpx
import traceback
from types import MethodType
from twikit import Client
from twikit.errors import BadRequest, Unauthorized, NotFound, Forbidden
from app.config import settings
from app.models.media import MediaType
from app.models.tweet import Tweet
from app.logger import setup_logger

try:
    from x_client_transaction import ClientTransaction as CommunityClientTransaction
    from x_client_transaction.utils import handle_x_migration_async, get_ondemand_file_url
except Exception:  # pragma: no cover - optional experiment dependency
    CommunityClientTransaction = None
    handle_x_migration_async = None
    get_ondemand_file_url = None

logger = setup_logger("twikit")


class CommunityTransactionAdapter:
    def __init__(self):
        self.home_page_response = None
        self.DEFAULT_ROW_INDEX = None
        self.DEFAULT_KEY_BYTES_INDICES = None
        self.key = None
        self.animation_key = None
        self._provider = None

    async def init(self, session, headers):
        if CommunityClientTransaction is None or handle_x_migration_async is None or get_ondemand_file_url is None:
            raise RuntimeError("x_client_transaction is not available")

        home_page_response = await handle_x_migration_async(session)
        ondemand_file_url = get_ondemand_file_url(home_page_response)
        ondemand_file_response = await session.request(method="GET", url=ondemand_file_url, headers=headers)
        provider = CommunityClientTransaction(home_page_response, ondemand_file_response.text)

        self._provider = provider
        self.home_page_response = provider.home_page_response
        self.DEFAULT_ROW_INDEX = provider.row_index
        self.DEFAULT_KEY_BYTES_INDICES = provider.key_bytes_indices
        self.key = provider.key
        self.animation_key = provider.animation_key

    def generate_transaction_id(self, method: str, path: str, response=None, key=None, animation_key=None, time_now=None):
        if self._provider is None:
            raise RuntimeError("Community transaction provider is not initialized")
        return self._provider.generate_transaction_id(
            method=method,
            path=path,
            home_page_response=response or self.home_page_response,
            key=key,
            animation_key=animation_key,
            time_now=time_now,
        )


class TwitterTwikit:
    def __init__(self):
        self.client: Optional[Client] = None
        self.cookies_file = "./data/twitter_cookies.json"

    def _create_client(self) -> Client:
        proxy = settings.proxy_url if settings.proxy_url else None
        logger.info("创建 twikit 客户端，代理: %s", proxy or "无")
        client = Client(language='en-US', proxy=proxy)
        client.http.timeout = httpx.Timeout(60.0, connect=30.0, read=60.0, write=60.0, pool=60.0)
        if CommunityClientTransaction is not None:
            logger.info("启用社区 transaction provider: x_client_transaction")
            client.client_transaction = CommunityTransactionAdapter()
        # 修复 twikit 2.3.3 bug: onboarding_task 等方法未携带完整 headers
        # 导致 Cloudflare 因缺少 User-Agent 而拦截请求返回 403
        client.http.headers.update({
            'User-Agent': client._user_agent,
            'Referer': 'https://x.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        original_request = client.request
        transaction_lock = asyncio.Lock()

        def _transaction_ready() -> bool:
            ct = client.client_transaction
            return bool(
                getattr(ct, 'home_page_response', None)
                and getattr(ct, 'DEFAULT_ROW_INDEX', None) is not None
                and getattr(ct, 'DEFAULT_KEY_BYTES_INDICES', None) is not None
                and hasattr(ct, 'key')
                and hasattr(ct, 'animation_key')
            )

        async def _ensure_transaction_ready() -> None:
            if _transaction_ready():
                return
            async with transaction_lock:
                if _transaction_ready():
                    return
                cookies_backup = client.get_cookies().copy()
                ct_headers = {
                    'Accept-Language': f'{client.language},{client.language.split("-")[0]};q=0.9',
                    'Cache-Control': 'no-cache',
                    'Referer': 'https://x.com/',
                    'User-Agent': client._user_agent,
                }
                await client.client_transaction.init(client.http, ct_headers)
                client.set_cookies(cookies_backup, clear_cookies=True)

        async def patched_request(self, method, url, *args, **kwargs):
            await _ensure_transaction_ready()
            url_text = str(url)
            if 'media/upload' in url_text and 'timeout' not in kwargs:
                kwargs['timeout'] = httpx.Timeout(300.0, connect=30.0, read=300.0, write=300.0, pool=300.0)
                logger.info('媒体上传请求启用长超时: %s', url_text)
            return await original_request(method, url, *args, **kwargs)

        client.request = MethodType(patched_request, client)
        return client

    async def init_client(self):
        logger.info("初始化 twikit 客户端")
        self.client = self._create_client()

        if os.path.exists(self.cookies_file):
            try:
                import json as _json
                with open(self.cookies_file, 'r') as _f:
                    _raw = _json.load(_f)
                # Only pass auth_token and ct0 to twikit; ignore metadata fields
                _cookies = {k: v for k, v in _raw.items() if k in ('auth_token', 'ct0')}
                if not _cookies.get('auth_token') or not _cookies.get('ct0'):
                    raise ValueError("Missing auth_token or ct0 in cookie file")
                self.client.set_cookies(_cookies, clear_cookies=True)
                self.client.http.headers['x-csrf-token'] = _cookies['ct0']
                logger.info("从 cookie 文件恢复登录状态成功，跳过验证直接使用")
                return
            except Exception as e:
                logger.warning("加载 cookie 失败，将重新登录: %s", e)
                if os.path.exists(self.cookies_file):
                    os.remove(self.cookies_file)

        await self.login()

    async def login(self, username: str = None, email: str = None, password: str = None):
        if not self.client:
            self.client = self._create_client()

        login_username = username or settings.twitter_username
        login_email = email or settings.twitter_email
        login_password = password or settings.twitter_password

        if not login_username or not login_email or not login_password:
            raise ValueError("Twitter 账号信息未配置，请在 .env 文件或前端 Settings 页面配置")

        logger.info("开始登录 Twitter (v2.x ui_metrics 已启用)，账号: %s", login_username)

        # 删除旧的 cookie 文件（如果存在）
        if os.path.exists(self.cookies_file):
            logger.info("删除旧的 cookie 文件")
            os.remove(self.cookies_file)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info("登录尝试 %d/%d", attempt + 1, max_retries)
                await self.client.login(
                    auth_info_1=login_username,
                    auth_info_2=login_email,
                    password=login_password,
                    enable_ui_metrics=True
                )
                self.client.save_cookies(self.cookies_file)
                logger.info("登录成功，cookie 已保存")
                return
            except BadRequest as e:
                error_msg = str(e)
                logger.error("登录失败 (尝试 %d/%d): %s", attempt + 1, max_retries, error_msg)

                # 详细的错误分类和提示
                if "Could not log you in now" in error_msg or "399" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                        logger.info("等待 %d 秒后重试...", wait_time)
                        await asyncio.sleep(wait_time)
                        # 重新创建客户端
                        self.client = self._create_client()
                    else:
                        raise Exception(
                            f"❌ 登录失败: Twitter 服务端临时限制 (错误 399)\n\n"
                            f"【错误原因】\n"
                            f"Twitter 检测到异常登录行为，暂时拒绝了登录请求。\n\n"
                            f"【可能原因】\n"
                            f"1. IP 地址被标记为可疑（代理IP质量差或被滥用）\n"
                            f"2. 登录频率过高（短时间内多次尝试）\n"
                            f"3. 账号密码错误导致多次失败\n"
                            f"4. 缺少有效的代理配置（中国大陆必需）\n\n"
                            f"【当前配置】\n"
                            f"- 代理: {settings.proxy_url or '❌ 未配置'}\n"
                            f"- 账号: {login_username}\n\n"
                            f"【解决方案】\n"
                            f"1. 检查代理配置是否正确（.env 中的 PROXY_URL）\n"
                            f"2. 更换代理 IP（使用高质量的住宅代理）\n"
                            f"3. 等待 2-3 小时后重试\n"
                            f"4. 确认账号密码正确\n"
                            f"5. 先在浏览器中手动登录一次 https://x.com\n\n"
                            f"【原始错误】\n{error_msg}"
                        )
                elif "326" in error_msg or "locked" in error_msg.lower():
                    raise Exception(
                        f"❌ 登录失败: 账号被锁定 (错误 326)\n\n"
                        f"【错误原因】\n"
                        f"Twitter 检测到账号存在异常活动，已暂时锁定。\n\n"
                        f"【解决方案】\n"
                        f"1. 访问 https://x.com 在浏览器中登录\n"
                        f"2. 完成 Twitter 要求的验证（手机验证、邮箱验证等）\n"
                        f"3. 解锁后等待 1 小时再使用 twikit 登录\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif "403" in error_msg or "Forbidden" in error_msg:
                    raise Exception(
                        f"❌ 登录失败: 请求被拒绝 (错误 403)\n\n"
                        f"【错误原因】\n"
                        f"Cloudflare 或 Twitter 防火墙拦截了请求。\n\n"
                        f"【可能原因】\n"
                        f"1. User-Agent 不正确或缺失\n"
                        f"2. 请求头不完整\n"
                        f"3. IP 被 Cloudflare 封禁\n"
                        f"4. 代理配置错误\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置'}\n\n"
                        f"【解决方案】\n"
                        f"1. 升级 twikit 到最新版本: pip install -U twikit\n"
                        f"2. 更换代理 IP\n"
                        f"3. 检查代理是否能正常访问 https://x.com\n"
                        f"4. 确认 twikit 版本 >= 2.3.3\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    raise Exception(
                        f"❌ 登录失败: 认证失败 (错误 401)\n\n"
                        f"【错误原因】\n"
                        f"账号密码不正确，或账号状态异常。\n\n"
                        f"【解决方案】\n"
                        f"1. 检查用户名、邮箱、密码是否正确\n"
                        f"2. 确认账号未被停用或删除\n"
                        f"3. 尝试在浏览器中登录 https://x.com 验证账号状态\n"
                        f"4. 如果最近修改过密码，请更新 .env 配置\n\n"
                        f"【当前账号】\n"
                        f"- 用户名: {login_username}\n"
                        f"- 邮箱: {login_email}\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif "password" in error_msg.lower() or "credentials" in error_msg.lower():
                    raise Exception(
                        f"❌ 登录失败: 账号密码错误\n\n"
                        f"【错误原因】\n"
                        f"提供的用户名、邮箱或密码不正确。\n\n"
                        f"【当前配置】\n"
                        f"- 用户名: {login_username}\n"
                        f"- 邮箱: {login_email}\n"
                        f"- 密码: {'*' * len(login_password) if login_password else '❌ 未配置'}\n\n"
                        f"【解决方案】\n"
                        f"1. 检查 .env 文件中的 TWITTER_USERNAME、TWITTER_EMAIL、TWITTER_PASSWORD\n"
                        f"2. 确认密码没有特殊字符导致的转义问题\n"
                        f"3. 尝试在浏览器中登录验证账号密码\n"
                        f"4. 如果使用了两步验证，可能需要应用专用密码\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                else:
                    # 未知的 BadRequest 错误
                    raise Exception(
                        f"❌ 登录失败: Twitter API 请求错误\n\n"
                        f"【错误类型】BadRequest\n\n"
                        f"【可能原因】\n"
                        f"1. 请求参数格式错误\n"
                        f"2. Twitter API 返回了未预期的错误\n"
                        f"3. 网络连接不稳定\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置'}\n"
                        f"- 账号: {login_username}\n\n"
                        f"【解决方案】\n"
                        f"1. 检查网络连接和代理配置\n"
                        f"2. 查看完整错误信息并搜索解决方案\n"
                        f"3. 尝试更新 twikit: pip install -U twikit\n"
                        f"4. 如果问题持续，请提交 issue 到 twikit 项目\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
            except Unauthorized as e:
                error_msg = str(e)
                logger.error("登录失败 (认证错误): %s", error_msg)
                raise Exception(
                    f"❌ 登录失败: Cookie 已过期或无效 (Unauthorized)\n\n"
                    f"【错误原因】\n"
                    f"保存的 Cookie 已失效，需要重新登录。\n\n"
                    f"【解决方案】\n"
                    f"1. 删除旧的 cookie 文件: rm -f ./data/twitter_cookies.json\n"
                    f"2. 重新登录\n"
                    f"3. 如果问题持续，检查账号状态\n\n"
                    f"【原始错误】\n{error_msg}"
                )
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
                error_type = type(e).__name__
                logger.error("登录失败: %s", error_msg)
                logger.error("完整错误堆栈: %s", traceback.format_exc())

                # 根据异常类型提供详细提示
                if "timeout" in error_msg.lower() or "TimeoutError" in error_type:
                    raise Exception(
                        f"❌ 登录失败: 网络超时 (Timeout)\n\n"
                        f"【错误原因】\n"
                        f"连接 Twitter 服务器超时，可能是网络问题或代理问题。\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置'}\n\n"
                        f"【解决方案】\n"
                        f"1. 检查网络连接是否正常\n"
                        f"2. 检查代理服务是否运行（端口 7896）\n"
                        f"3. 测试代理: curl -x {settings.proxy_url or 'http://127.0.0.1:7896'} https://x.com\n"
                        f"4. 尝试更换代理服务器\n"
                        f"5. 增加超时时间（如果网络较慢）\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif "connection" in error_msg.lower() or "ConnectionError" in error_type:
                    raise Exception(
                        f"❌ 登录失败: 网络连接失败 (Connection Error)\n\n"
                        f"【错误原因】\n"
                        f"无法连接到 Twitter 服务器。\n\n"
                        f"【可能原因】\n"
                        f"1. 代理配置错误或代理服务未运行\n"
                        f"2. 网络连接中断\n"
                        f"3. Twitter 服务器暂时不可用\n"
                        f"4. 防火墙阻止了连接\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置（中国大陆必需）'}\n\n"
                        f"【解决方案】\n"
                        f"1. 确认代理服务正在运行: ps aux | grep clash\n"
                        f"2. 测试代理连接: curl -x {settings.proxy_url or 'http://127.0.0.1:7896'} -I https://x.com\n"
                        f"3. 检查 .env 中的 PROXY_URL 配置\n"
                        f"4. Docker 容器内使用: http://host.docker.internal:7896\n"
                        f"5. 宿主机使用: http://127.0.0.1:7896\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif "proxy" in error_msg.lower():
                    raise Exception(
                        f"❌ 登录失败: 代理错误 (Proxy Error)\n\n"
                        f"【错误原因】\n"
                        f"代理服务器配置错误或无法连接。\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置'}\n\n"
                        f"【解决方案】\n"
                        f"1. 检查代理地址格式: http://host:port\n"
                        f"2. 确认代理服务正在运行\n"
                        f"3. Docker 容器内必须使用: http://host.docker.internal:7896\n"
                        f"4. 测试代理: curl -x {settings.proxy_url} -I https://x.com\n"
                        f"5. 如果不需要代理，设置 PROXY_URL 为空\n\n"
                        f"【原始错误】\n{error_msg}"
                    )
                elif not str(e):
                    # 空错误信息，通常是网络问题
                    raise Exception(
                        f"❌ 登录失败: 未知错误（错误信息为空）\n\n"
                        f"【错误类型】{error_type}\n\n"
                        f"【可能原因】\n"
                        f"1. 网络连接失败（最常见）\n"
                        f"2. 代理配置错误\n"
                        f"3. Twitter 服务器无响应\n"
                        f"4. 请求被防火墙拦截\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置（中国大陆必需）'}\n"
                        f"- 账号: {login_username}\n\n"
                        f"【解决方案】\n"
                        f"1. 配置代理: PROXY_URL=http://host.docker.internal:7896\n"
                        f"2. 确认代理服务运行: systemctl status clash\n"
                        f"3. 测试网络: curl -x http://127.0.0.1:7896 https://x.com\n"
                        f"4. 查看完整日志: docker compose logs backend -f\n\n"
                        f"【调试信息】\n"
                        f"错误堆栈:\n{traceback.format_exc()}"
                    )
                else:
                    raise Exception(
                        f"❌ 登录失败: {error_type}\n\n"
                        f"【错误信息】\n{error_msg}\n\n"
                        f"【当前配置】\n"
                        f"- 代理: {settings.proxy_url or '❌ 未配置'}\n"
                        f"- 账号: {login_username}\n\n"
                        f"【解决方案】\n"
                        f"1. 查看上方的错误信息\n"
                        f"2. 搜索错误信息寻找解决方案\n"
                        f"3. 检查网络和代理配置\n"
                        f"4. 查看完整日志: docker compose logs backend --tail 100\n\n"
                        f"【调试信息】\n"
                        f"错误堆栈:\n{traceback.format_exc()}"
                    )

    async def get_me(self) -> dict:
        if not self.client:
            await self.init_client()

        user = await self.client.user()
        logger.info("获取当前用户成功: @%s", user.screen_name)
        return {"id": user.id, "username": user.screen_name, "name": user.name}

    async def post_tweet(self, content: str, media_paths: List[str] = []) -> str:
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                logger.error("Twitter 未登录，无法发布推文: %s", e)
                raise ValueError("Twitter 未登录，请先在 Settings 页面登录 Twitter 账号")

        media_ids = []
        if media_paths:
            for path in media_paths:
                guessed_type, _ = mimetypes.guess_type(path)
                upload_kwargs = {
                    'wait_for_completion': True,
                }
                if guessed_type:
                    upload_kwargs['media_type'] = guessed_type
                if guessed_type and guessed_type.startswith('video'):
                    upload_kwargs['media_category'] = 'tweet_video'
                elif guessed_type == 'image/gif':
                    upload_kwargs['media_category'] = 'tweet_gif'

                logger.info("上传媒体文件: %s, mime=%s, kwargs=%s", path, guessed_type, upload_kwargs)
                try:
                    media_id = await self.client.upload_media(path, **upload_kwargs)
                except Exception as e:
                    logger.exception("媒体上传失败: path=%s, mime=%s, error=%r", path, guessed_type, e)
                    detail = str(e).strip() or repr(e)
                    raise ValueError(f"媒体上传失败: {detail}") from e
                media_ids.append(media_id)
                logger.debug("媒体上传成功，media_id: %s", media_id)

        logger.info("发布推文，内容长度: %d 字符，媒体数: %d", len(content), len(media_ids))
        if media_ids:
            tweet = await self.client.create_tweet(text=content, media_ids=media_ids)
        else:
            tweet = await self.client.create_tweet(text=content)

        logger.info("推文发布成功，twitter_id: %s", tweet.id)
        return tweet.id

    async def search_tweets(self, query: str, count: int = 20) -> List[dict]:
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                logger.error("Twitter 未登录，无法搜索: %s", e)
                raise ValueError("Twitter 未登录，请先在 Settings 页面登录 Twitter 账号")

        logger.info("搜索推文，关键词: %s，数量: %d", query, count)
        try:
            results = await self.client.search_tweet(query, product='Top', count=count)
            tweets = []
            for t in results:
                tweets.append({
                    "id": t.id,
                    "text": t.text,
                    "author_name": t.user.name,
                    "author_username": t.user.screen_name,
                    "author_verified": t.user.is_blue_verified,
                    "like_count": t.favorite_count,
                    "retweet_count": t.retweet_count,
                    "reply_count": t.reply_count,
                    "view_count": t.view_count,
                    "created_at": str(t.created_at),
                    "url": f"https://x.com/{t.user.screen_name}/status/{t.id}",
                })
            logger.info("搜索完成，返回 %d 条结果", len(tweets))
            return tweets
        except Exception as e:
            logger.error("搜索推文失败，关键词: %s，错误: %s", query, e)
            raise

    async def reply_tweet(self, tweet_id: str, content: str) -> str:
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                logger.error("Twitter 未登录，无法回复推文: %s", e)
                raise ValueError("Twitter 未登录，请先在 Settings 页面登录 Twitter 账号")

        logger.info("回复推文 %s，内容长度: %d 字符", tweet_id, len(content))
        try:
            tweet = await self.client.create_tweet(text=content, reply_to=tweet_id)
            logger.info("回复成功，reply_id: %s", tweet.id)
            return tweet.id
        except Exception as e:
            logger.error("回复推文失败，tweet_id: %s，错误: %s", tweet_id, e)
            raise


    async def retweet(self, tweet_id: str) -> str:
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                raise ValueError("Twitter not logged in") from e

        logger.info("Retweeting tweet %s", tweet_id)
        await self.client.retweet(tweet_id)
        logger.info("Retweet successful")
        return tweet_id

    async def quote_tweet(self, tweet_url: str, content: str, media_paths: List[str] = []) -> str:
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                raise ValueError("Twitter not logged in") from e

        media_ids = []
        if media_paths:
            for path in media_paths:
                media_id = await self.client.upload_media(path, wait_for_completion=True)
                media_ids.append(media_id)
                logger.debug("Media uploaded for quote tweet, media_id: %s", media_id)

        logger.info("Quote tweeting %s, content length: %d, media count: %d", tweet_url, len(content), len(media_ids))
        tweet = await self.client.create_tweet(
            text=content,
            quote_tweet_url=tweet_url,
            media_ids=media_ids if media_ids else None
        )
        logger.info("Quote tweet successful, id: %s", tweet.id)
        return tweet.id

    async def get_mentions(self, count: int = 40) -> List[dict]:
        """
        Fetch recent mention notifications (replies to our tweets/comments).

        twikit's get_notifications('Mentions') parses globalObjects.notifications
        which is always empty for the Mentions endpoint. The actual data lives in
        globalObjects.tweets + timeline.instructions[addEntries], so we parse the
        raw v11 response directly.
        """
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                raise ValueError("Twitter not logged in") from e

        logger.info("Fetching mention notifications, count=%d", count)
        try:
            response, _ = await self.client.v11.notifications_mentions(count, None)

            global_objects = response.get('globalObjects', {})
            tweets_data = global_objects.get('tweets', {})
            users_data = global_objects.get('users', {})

            # Extract notification entries from timeline instructions
            entries = []
            for inst in response.get('timeline', {}).get('instructions', []):
                if 'addEntries' in inst:
                    entries = inst['addEntries'].get('entries', [])
                    break

            mentions = []
            for entry in entries:
                entry_id = entry.get('entryId', '')
                if not entry_id.startswith('notification-'):
                    continue

                try:
                    tweet_id = entry['content']['item']['content']['tweet']['id']
                except (KeyError, TypeError):
                    continue

                tweet_data = tweets_data.get(tweet_id)
                if not tweet_data:
                    continue

                user_id = tweet_data.get('user_id_str')
                user_data = users_data.get(user_id, {})

                in_reply_to = tweet_data.get('in_reply_to_status_id_str')
                text = tweet_data.get('full_text') or tweet_data.get('text') or ''
                screen_name = user_data.get('screen_name', '')
                user_name = user_data.get('name', '')
                created_at = tweet_data.get('created_at', '')

                # notification_id is the entry sort index (stable across polls)
                notification_id = entry.get('sortIndex', entry_id)

                mentions.append({
                    "notification_id": notification_id,
                    "tweet_id": tweet_id,
                    "tweet_text": text,
                    "in_reply_to": in_reply_to,
                    "from_username": screen_name,
                    "from_user_id": user_id,
                    "from_user_name": user_name,
                    "created_at": created_at,
                    "created_at_datetime": None,
                })

            logger.info("Fetched %d mention notifications", len(mentions))
            return mentions
        except Exception as e:
            logger.error("Failed to fetch mentions: %s", e)
            raise

    async def get_tweet_by_id(self, tweet_id: str) -> dict:
        """Fetch a single tweet by ID, returns basic dict."""
        if not self.client:
            try:
                await self.init_client()
            except Exception as e:
                raise ValueError("Twitter not logged in") from e

        tweet = await self.client.get_tweet_by_id(tweet_id)
        return {
            "id": tweet.id,
            "text": tweet.text or "",
            "in_reply_to": getattr(tweet, 'in_reply_to', None),
            "author_username": tweet.user.screen_name if tweet.user else "",
            "author_id": tweet.user.id if tweet.user else "",
            "created_at": str(getattr(tweet, 'created_at', '')),
        }


_twikit_instance: Optional[TwitterTwikit] = None


async def get_twitter_twikit() -> TwitterTwikit:
    global _twikit_instance
    if _twikit_instance is None:
        _twikit_instance = TwitterTwikit()
        await _twikit_instance.init_client()
    return _twikit_instance


def reset_twitter_twikit():
    global _twikit_instance
    _twikit_instance = None


async def test_connection_twikit() -> str:
    twitter = await get_twitter_twikit()
    me = await twitter.get_me()
    return me["username"]


async def publish_tweet_twikit(tweet: Tweet) -> str:
    twitter = await get_twitter_twikit()
    media_paths = [m.filepath for m in tweet.media_items] if tweet.media_items else []
    return await twitter.post_tweet(tweet.content, media_paths)


async def search_tweets_twikit(query: str, count: int = 20) -> List[dict]:
    twitter = await get_twitter_twikit()
    return await twitter.search_tweets(query, count)


async def reply_tweet_twikit(tweet_id: str, content: str) -> str:
    twitter = await get_twitter_twikit()
    return await twitter.reply_tweet(tweet_id, content)


async def retweet_tweet_twikit(tweet_id: str) -> str:
    twitter = await get_twitter_twikit()
    return await twitter.retweet(tweet_id)


async def quote_tweet_twikit(tweet_url: str, content: str, media_paths: List[str] = []) -> str:
    twitter = await get_twitter_twikit()
    return await twitter.quote_tweet(tweet_url, content, media_paths)


async def get_mentions_twikit(count: int = 40) -> List[dict]:
    twitter = await get_twitter_twikit()
    return await twitter.get_mentions(count)


async def get_tweet_by_id_twikit(tweet_id: str) -> dict:
    twitter = await get_twitter_twikit()
    return await twitter.get_tweet_by_id(tweet_id)
