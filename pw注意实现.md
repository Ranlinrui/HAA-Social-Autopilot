# Playwright 方案实现注意事项

> 本文档记录在当前项目中实现 Playwright 替代方案（Phase 7.6）的关键注意点。
> **核心原则：不破坏现有 twikit 功能，通过环境变量切换引擎。**

---

## 一、检测风险（最重要）

Twitter 的反爬是多层的，标准 Playwright 在 2025/2026 年基本必被检测。

### 1.1 必须解决的检测点

**CDP Runtime.enable 泄漏（最关键）**
Playwright 通过 CDP 协议控制浏览器，会发送 `Runtime.enable` 命令。这个命令会产生可被检测的副作用——Twitter 的反爬脚本通过 `console.log(new Error())` 的 stack getter 触发时机来判断是否在 CDP 环境中。标准 Playwright 无法绕过这个检测。

**navigator.webdriver = true**
标准 Playwright 会把这个属性设为 true，是最基础的检测点。

**User-Agent 包含 HeadlessChrome**
Headless Chromium 的 UA 字符串里有 `HeadlessChrome/xxx`，Twitter 会检查这个子串。

**sec-ch-ua 客户端提示头**
即使手动改了 UA，`sec-ch-ua` 请求头里仍然会有 `"HeadlessChrome"`，很多 stealth 插件漏掉了这个。

**Playwright 注入的全局变量**
`window.__playwright__binding__` 和 `window.__pwInitScripts` 会被检测脚本遍历 window 属性时发现。

### 1.2 推荐方案：用 Patchright 替代标准 Playwright

`patchright` 是 Python 版 Playwright 的 drop-in 替代，专门修复了 CDP Runtime.enable 泄漏问题。

```bash
pip install patchright
patchright install chrome  # 安装真实 Chrome，不是 Chromium
```

```python
from patchright.async_api import async_playwright
# 其余用法和标准 playwright 完全一样
```

关键区别：
- 用隔离的 JS 执行上下文替代 `Runtime.enable`
- 自动加 `--disable-blink-features=AutomationControlled`
- 自动去掉 `--enable-automation` 标志
- 安装真实 Chrome（Twitter 对 Chromium 更敏感）

> **注意**：`undetected-playwright-python` 已于 2024 年 11 月归档，不要用。
> `playwright-stealth` 不修复 CDP 泄漏，只能作为补充，不能作为主方案。

### 1.3 行为层面的反检测

即使解决了指纹问题，行为模式也会暴露：
- 点击间隔太均匀（固定 sleep）→ 用随机延迟 `random.uniform(0.8, 2.5)`
- 打字速度太快 → 用 `type()` 而不是 `fill()`，或者 `fill()` 后加随机延迟
- 没有鼠标移动 → 操作前先 `hover()` 一下目标元素
- 没有滚动行为 → 偶尔加 `page.mouse.wheel(0, 300)`

---

## 二、会话持久化

### 2.1 推荐：storage_state（轻量）

```python
# 首次登录后保存
await context.storage_state(path="./data/pw_twitter_state.json")

# 后续启动时加载
context = await browser.new_context(
    storage_state="./data/pw_twitter_state.json"
)
```

state 文件包含 cookies + localStorage + IndexedDB，Twitter 三个都用来维持登录状态。

### 2.2 备选：launch_persistent_context（完整 Profile）

```python
context = await p.chromium.launch_persistent_context(
    user_data_dir="./data/pw_profile",
    channel="chrome",
    headless=True,
    args=["--no-sandbox", "--disable-dev-shm-usage"]
)
```

更接近真实用户，但磁盘占用更大。有一个已知 bug（Playwright issue #36139）：某些版本下 cookies 不能跨进程持久化，遇到时回退到 storage_state。

### 2.3 与现有 twikit cookie 的关系

twikit 的 cookie 存在 `./data/twitter_cookies.json`，Playwright 的 state 存在 `./data/pw_twitter_state.json`，两者完全独立，不要混用。

---

## 三、提取推文 ID（关键难点）

发推后 Twitter 不会直接展示推文 ID，需要主动提取。

### 3.1 拦截 GraphQL 响应（最可靠）

发推时 Twitter 前端会调用 `POST https://x.com/i/api/graphql/{queryId}/CreateTweet`，响应里有推文 ID。

```python
async def post_tweet_and_get_id(page, text: str) -> str:
    async with page.expect_response(
        lambda r: "CreateTweet" in r.url and r.status == 200
    ) as response_info:
        await page.locator('[data-testid="tweetTextarea_0"]').fill(text)
        await page.locator('[data-testid="tweetButtonInline"]').click()

    response = await response_info.value
    data = await response.json()

    # 主路径
    try:
        return data["data"]["create_tweet"]["tweet_results"]["result"]["rest_id"]
    except (KeyError, TypeError):
        pass
    # 备用路径
    try:
        return data["data"]["create_tweet"]["tweet_results"]["result"]["legacy"]["id_str"]
    except (KeyError, TypeError):
        return None
```

**注意**：URL 里的 `queryId` 是哈希值，会定期变化，匹配时用 `"CreateTweet" in r.url` 而不是完整 URL。

### 3.2 备选：从跳转 URL 提取

发推后 Twitter 有时会跳转到推文永久链接：

```python
await page.wait_for_url("**/status/**", timeout=10000)
tweet_id = page.url.split("/status/")[-1].split("?")[0]
```

不稳定，只作为 fallback。

### 3.3 推文 ID 精度问题

Twitter 的 Snowflake ID 是 64 位整数，超过 JavaScript `Number` 的安全范围（53 位）。Python 没有这个问题，但序列化成 JSON 时要用字符串存储，不要用 int。

---

## 四、稳定的 DOM 选择器

Twitter 用 React 渲染，CSS class 经常变，`data-testid` 属性相对稳定。

```python
# 发推相关
'[data-testid="SideNav_NewTweet_Button"]'   # 首页"发推"按钮
'[data-testid="tweetTextarea_0"]'            # 推文输入框
'[data-testid="tweetButtonInline"]'          # 提交按钮

# 回复
'[data-testid="reply"]'                      # 回复按钮

# 转发
'[data-testid="retweet"]'                    # 转发按钮
'[data-testid="retweetConfirm"]'             # 确认转发

# 引用转发
'[data-testid="quoteTweet"]'                 # 引用转发选项

# 媒体上传
'input[data-testid="fileInput"]'             # 文件上传 input

# 推文列表
'[data-testid="tweet"]'                      # 推文卡片容器
'[data-testid="tweetText"]'                  # 推文正文

# 登录
'input[autocomplete="username"]'
'input[autocomplete="current-password"]'
```

**操作前必须等待元素可见**，Twitter 的 React 渲染是异步的：

```python
await page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=10000)
```

---

## 五、Docker 环境配置

### 5.1 Dockerfile 需要额外的系统依赖

当前 Dockerfile 用 `python:3.12-slim`，运行 Chromium 需要额外的系统库：

```dockerfile
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    fonts-liberation fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install patchright
RUN patchright install chrome
```

**注意**：`fonts-noto-cjk` 是中文字体，Twitter 中文内容渲染需要，否则中文显示为方块，可能影响截图调试。

### 5.2 必须的启动参数

```python
args = [
    "--no-sandbox",              # 容器内以 root 运行时必须
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",   # Docker 默认 /dev/shm 只有 64MB，不够用
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--single-process",          # 内存受限环境可选
]
```

### 5.3 内存消耗

Chromium 进程本身占用 200-500MB 内存。如果容器内存限制较低，需要：
- 用 `--single-process` 减少进程数
- 操作完成后及时关闭不需要的 page
- 不要同时开多个 context

### 5.4 代理配置

当前项目用 `http://host.docker.internal:7896` 访问宿主机代理，Playwright 同样支持：

```python
context = await browser.new_context(
    proxy={"server": "http://host.docker.internal:7896"}
)
```

---

## 六、与现有代码的接口兼容

### 6.1 必须保持的接口

`twitter_playwright.py` 需要提供和 `twitter_twikit.py` 完全相同的对外接口，让 `twitter_api.py` 可以无缝切换：

```python
# twitter_api.py 切换逻辑（新增）
async def _get_engine():
    engine = os.getenv("TWITTER_ENGINE", "twikit")
    if engine == "playwright":
        from app.services.twitter_playwright import get_twitter_playwright
        return await get_twitter_playwright()
    else:
        from app.services.twitter_twikit import get_twitter_twikit
        return await get_twitter_twikit()
```

### 6.2 monitor_service.py 依赖的对象形状

monitor_service 通过 `get_twitter_client()` 拿到 client，然后调用：

```python
client.get_user_by_screen_name(username)  # 返回 user 对象
client.get_user_tweets(user_id, 'Tweets', count=5)  # 返回 tweet 列表
```

访问的属性：
- `user.id`、`user.name`
- `tweet.id`、`tweet.text`、`tweet.full_text`、`tweet.created_at_datetime`

Playwright 方案需要返回同样形状的对象（可以用 dataclass 或 SimpleNamespace 模拟）。

### 6.3 search_tweets 返回格式

engage.py 的搜索结果需要：

```python
{
    "id": str,
    "text": str,
    "author_name": str,
    "author_username": str,
    "author_verified": bool,
    "like_count": int,
    "retweet_count": int,
    "reply_count": int,
    "view_count": str,
    "created_at": str,
    "url": str
}
```

Playwright 方案从 DOM 解析这些数据，或者拦截 Twitter 的 GraphQL 搜索响应（`SearchTimeline` 接口）。

---

## 七、异步集成注意事项

### 7.1 Playwright 的 async 和 FastAPI 的兼容性

Playwright Python 是纯 async 的，和 FastAPI 兼容。但有一个坑：**Playwright 的 async_playwright() 上下文管理器不能跨请求复用**，需要在应用启动时初始化，关闭时清理。

```python
# 在 FastAPI lifespan 里管理 Playwright 生命周期
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await pw_service.init()
    yield
    # shutdown
    await pw_service.close()

app = FastAPI(lifespan=lifespan)
```

### 7.2 并发操作的限制

一个 Playwright browser context 同一时间只能安全地执行一个操作（Twitter 的 React 状态机不支持并发操作）。需要用 `asyncio.Lock` 串行化所有 Twitter 操作：

```python
class TwitterPlaywright:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def create_tweet(self, text: str) -> str:
        async with self._lock:
            # ... 操作 ...
```

---

## 八、实现优先级建议

按照从易到难、风险从低到高的顺序：

1. **发推 + 获取 ID**（GraphQL 拦截方案，最核心）
2. **回复推文**（和发推类似，多一步导航）
3. **转发 / 引用转发**（点击操作，相对简单）
4. **搜索推文**（拦截 SearchTimeline GraphQL 响应）
5. **获取用户推文**（拦截 UserTweets GraphQL 响应，用于监控）
6. **上传媒体**（最复杂，需要处理文件 input + 等待上传完成）

---

## 九、切换时机和回退策略

**切换到 Playwright 的条件：**
- twikit 连续 3 次 `Unauthorized` 且重新登录无效
- 账号触发 `AccountLocked`（Arkose）且自动解锁失败
- twikit 请求持续被 403/429 拦截

**切换方式：**
```bash
# .env 文件
TWITTER_ENGINE=playwright
```
重启容器生效，twikit 代码完全不动。

**回退方式：**
```bash
TWITTER_ENGINE=twikit
```

---

## 十、已知风险和局限

| 风险 | 说明 | 缓解 |
|------|------|------|
| Twitter UI 变更 | data-testid 属性可能改变 | 定期测试，维护选择器 |
| 内存消耗高 | Chromium 200-500MB | 单例复用，及时关闭 page |
| 操作速度慢 | 每次操作需等待页面渲染（1-5s） | 仅在 twikit 失败时切换 |
| 首次登录需人工 | 可能触发验证码 | 首次在有界面环境登录，保存 state |
| Patchright 维护风险 | 第三方库，可能停止维护 | 关注 GitHub，有备用方案 |
| GraphQL 结构变化 | Twitter 内部 API 不稳定 | 多路径解析，加 try/except |
