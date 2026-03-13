# HAA-Social-Autopilot

**Hyper Alpha Arena 社交媒体自动化推广工具**

HAA (Hyper Alpha Arena) 的低成本用户增长引擎。通过 Twitter/X 平台的自动化内容发布、效果追踪和智能互动，持续吸引潜在用户到 HAA 平台。

---

## 项目目标

本项目唯一目的：**低成本为 HAA 吸引潜在用户**。HAA 的商业模式是用户越多收益越高，本工具是 HAA 的增长获客引擎。

- 通过 Twitter/X 实现不投流的有机增长
- 自动化内容发布 + 智能互动，降低运营人力成本
- 数据驱动优化，持续提升获客效率
- 完整的获客漏斗：内容曝光 -> 教程引导 -> 用户注册

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Web管理后台                             │
│              React + TailwindCSS + shadcn/ui                │
├─────────────────────────────────────────────────────────────┤
│  - 推文管理（创建/编辑/删除/排期）                            │
│  - 发布日历（可视化排期视图）                                 │
│  - 素材库（图片/视频上传管理）                                │
│  - 数据看板（发布记录/状态追踪）                              │
│  - 系统设置（Twitter前端登录/LLM配置）                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        后端服务                              │
│                FastAPI + SQLite + APScheduler               │
├─────────────────────────────────────────────────────────────┤
│  - RESTful API（推文CRUD/素材管理/配置管理）                  │
│  - Twitter发布引擎（twikit，免费无限制）                    │
│  - LLM内容生成服务（OpenAI兼容接口）                          │
│  - 定时任务调度器（排期发布执行）                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 技术栈

### 后端
| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web框架 | FastAPI | 高性能异步Python框架 |
| 数据库 | SQLite | 轻量级，无需额外部署 |
| ORM | SQLAlchemy | 数据库操作抽象 |
| 调度器 | APScheduler | 定时任务管理 |
| Twitter引擎 | twikit 2.3.3 | 免费无限制，唯一发布引擎，已启用 v2.x 反检测 |
| LLM客户端 | openai | OpenAI兼容接口 |

### 前端
| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | React 18 | 现代前端框架 |
| 构建工具 | Vite | 快速开发构建 |
| 样式 | TailwindCSS | 原子化CSS |
| UI组件 | shadcn/ui | 高质量组件库 |
| 状态管理 | Zustand | 轻量状态管理 |
| 日历组件 | react-big-calendar | 排期日历 |
| HTTP客户端 | axios | API请求 |

---

## 核心功能模块

### 1. 推文管理
- 创建/编辑/删除推文
- 支持纯文本、图片、视频类型
- 草稿保存
- 推文模板

### 2. 排期发布
- 可视化日历排期
- 支持设置具体发布时间
- 批量排期
- 发布队列管理

### 3. 发布引擎（twikit 2.3.3）
- 免费，无发布数量限制
- 通过模拟登录调用 Twitter 内部 API
- 支持发布推文、上传媒体、获取互动数据等
- Cookie 持久化，无需频繁登录
- v2.x 反检测：x_client_transaction + ui_metrics 模块已启用
- 需控制操作频率避免触发风控

### 4. LLM内容生成
- 支持OpenAI兼容API（GPT、Claude、Deepseek等）
- 预设推文生成提示词模板
- 一键生成推文内容
- 支持自定义主题/风格/长度

### 5. 素材库
- 图片上传管理
- 视频上传管理（受Twitter限制）
- 素材分类/标签
- 素材复用

### 6. 数据看板
- 发布历史记录
- 发布状态追踪（成功/失败/待发布）
- 失败重试机制

---

## 目录结构

```
HAA-Social-Autopilot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI入口
│   │   ├── config.py               # 配置管理
│   │   ├── database.py             # 数据库连接
│   │   ├── models/                 # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── tweet.py            # 推文模型
│   │   │   ├── media.py            # 素材模型
│   │   │   └── setting.py          # 配置模型
│   │   ├── schemas/                # Pydantic模型
│   │   │   ├── __init__.py
│   │   │   ├── tweet.py
│   │   │   ├── media.py
│   │   │   └── setting.py
│   │   ├── routers/                # API路由
│   │   │   ├── __init__.py
│   │   │   ├── tweets.py
│   │   │   ├── media.py
│   │   │   ├── settings.py
│   │   │   └── llm.py
│   │   ├── services/               # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── twitter_api.py      # Twitter发布统一入口
│   │   │   ├── twitter_twikit.py   # twikit引擎实现
│   │   │   ├── llm_service.py      # LLM内容生成
│   │   │   └── scheduler.py        # 定时任务
│   │   └── utils/                  # 工具函数
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── uploads/                    # 上传文件存储
│   ├── data/                       # SQLite数据库
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/             # 通用组件
│   │   │   ├── ui/                 # shadcn/ui组件
│   │   │   ├── Layout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   ├── pages/                  # 页面组件
│   │   │   ├── Dashboard.tsx       # 数据看板
│   │   │   ├── Tweets.tsx          # 推文管理
│   │   │   ├── Calendar.tsx        # 排期日历
│   │   │   ├── Media.tsx           # 素材库
│   │   │   └── Settings.tsx        # 系统设置
│   │   ├── stores/                 # 状态管理
│   │   │   └── index.ts
│   │   ├── services/               # API服务
│   │   │   └── api.ts
│   │   ├── types/                  # TypeScript类型
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── .env.example                    # 环境变量示例
├── .gitignore
├── docker-compose.yml              # Docker部署
├── Dockerfile
└── README.md
```

---

## 环境变量配置

```env
# Twitter 账号配置 (twikit) -- 也可在前端 Settings 页面直接登录配置
TWITTER_USERNAME=your_username
TWITTER_EMAIL=your_email@example.com
TWITTER_PASSWORD=your_password

# LLM配置
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o

# 服务配置
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

---

## 开发计划

### Phase 1: 项目初始化 -- 已完成
- [x] 创建项目结构
- [x] 配置后端依赖（requirements.txt / pyproject.toml）
- [x] 配置前端依赖（package.json）
- [x] 创建环境变量模板

### Phase 2: 后端核心开发 -- 已完成
- [x] 数据库模型设计（Tweet / Media / Setting）
- [x] 推文 CRUD API
- [x] 素材上传 API
- [x] 配置管理 API
- [x] LLM 内容生成 API

### Phase 3: 发布引擎 -- 已完成
- [x] twikit 集成（唯一发布引擎，免费无限制）
- [x] 发布统一入口（twitter_api.py -> twitter_twikit.py）
- [x] APScheduler 定时任务（排期发布 + 失败重试）
- [x] ~~tweepy / Playwright 已移除（2026.3.4），统一使用 twikit~~

### Phase 4: 前端开发 -- 已完成
- [x] React + Vite + TailwindCSS + shadcn/ui 脚手架
- [x] 布局组件（Sidebar / Header）
- [x] 推文管理页面（CRUD + 发布 + 排期）
- [x] 排期日历页面（月度视图）
- [x] 素材库页面（拖放上传 + 网格展示）
- [x] 系统设置页面（Twitter 前端登录 / LLM 配置 / 连接测试）
- [x] 数据看板页面（统计卡片 + 最近推文）

### Phase 5: Docker 部署 -- 已完成
- [x] 后端 Dockerfile
- [x] docker-compose.yml 多服务编排
- [x] 数据库自动初始化

### Phase 5.5: twikit v2.x 升级 + 前端 Twitter 登录 -- 已完成（2026.3.9）
- [x] twikit 从 v1.7.6 升级到 v2.3.3（requirements.txt 已更新）
- [x] 启用 v2.x 反检测：`enable_ui_metrics=True` + `x_client_transaction` 自动生效
- [x] `login()` 使用 v2.x `cookies_file` 参数简化 cookie 管理
- [x] Settings 页面新增 Twitter 账号登录表单（用户名/邮箱/密码）
- [x] 新增 `POST /api/settings/twitter-login` 接口，支持前端直接登录
- [x] 登录成功后凭证自动保存到数据库，刷新页面自动填充（密码不返回明文）
- [x] 支持密码已保存时免输密码重新登录
- [x] 全局 twikit 单例支持动态重置（登录新账号后自动切换）

### Phase 6: 效果追踪系统 -- 计划中
> 目标：知道什么内容有效，用数据驱动内容策略优化

- [ ] Tweet 模型扩展互动指标字段（likes / retweets / replies / views）
- [ ] 新建 TweetMetrics 模型，存储历史快照用于趋势分析
- [ ] twikit 扩展 `get_tweet_by_id()` 获取推文互动数据（免费）
- [ ] 定时任务：每 30-60 分钟自动拉取近 7 天已发布推文的互动数据
- [ ] 粉丝增长追踪：定期记录 followers_count 快照
- [ ] 新增 `/api/analytics` 路由（推文指标、汇总统计、趋势数据）
- [ ] Dashboard 扩展：互动量统计卡片、互动趋势图表
- [ ] 新建 Analytics 页面：推文效果排行、最佳发布时段分析、内容类型对比

### Phase 7: 智能互动自动化 -- 计划中
> 目标：主动触达潜在用户，从"等人来"变成"去找人"

- [ ] twikit 扩展互动方法（like / retweet / reply / follow / search）
- [ ] 新建 AutomationRule 模型（规则类型、触发条件、目标关键词、每日上限）
- [ ] 新建 AutomationLog 模型（执行日志，用于审计和频率控制）
- [ ] 关键词监控：定期搜索 "AI trading bot"、"crypto trading" 等相关话题
- [ ] 自动点赞：对目标话题下的高质量推文自动点赞，建立存在感
- [ ] 智能回复：LLM 生成有价值的回复（注意：2026.2 起 X 限制 API 自动回复，仅允许回复 @提及的推文，twikit 模式需谨慎控制频率）
- [ ] 目标用户关注：关注竞品粉丝和相关话题活跃用户（每日上限 20-30 次）
- [ ] 安全防护：操作间隔随机化（30s-5min）、每日总量上限、模拟人类作息时间
- [ ] 新建 Automation 管理页面：规则配置、执行日志、安全状态监控

### Phase 7.5: 名人账号监控与评论引流 -- 计划中
> 目标：在高流量账号下抢占评论区前排，精准触达目标用户

**核心策略：监控自动化 + 执行人工化**

由于 X 平台 2026.2 起限制 API 自动回复（仅允许回复 @提及的推文），纯自动化评论已不可行。推荐方案是自动监控+人工评论，既保证响应速度又规避封号风险。

#### 技术实现

**监控层（自动化）**
- [ ] 新建 MonitoredAccount 模型（账号列表、监控优先级、轮询间隔）
- [ ] 使用 twikit `get_user_tweets()` 或 SocialData API 轮询目标账号
- [ ] 每 2-5 分钟检查新推文，使用 `since_id` 增量获取
- [ ] 成本估算：监控 50 个账号，X API 约 $10-50/天，SocialData API 约 $2-10/天

**通知层（自动化）**
- [ ] Telegram Bot 即时推送新推文通知
- [ ] 通知内容：推文链接、内容摘要、作者信息、发布时间
- [ ] 推送优先级：第一优先级账号（CZ、Vitalik）立即推送，其他分级推送

**执行层（人工）**
- [ ] 人工判断是否值得评论（15 分钟黄金窗口）
- [ ] 人工撰写有针对性的评论（可参考 AI 生成的草稿）
- [ ] 人工发布评论（通过 Web 界面或 Twitter 客户端）

#### 推荐监控账号

**第一优先级（每 2 分钟监控）**
- `@binance` (1000万+粉丝)
- `@cz_binance` (970万+粉丝)
- `@VitalikButerin` (510万+粉丝)

**第二优先级（每 5 分钟监控）**
- `@coinbase`、`@okx`、`@Bybit_Official`
- `@saylor` (Michael Saylor)

**第三优先级（每 15 分钟监控）**
- `@krakenfx`、`@gate_io`
- `@CryptoHayes` (Arthur Hayes)
- `@RaoulGMI` (Raoul Pal)

#### 评论策略

**抢前排技巧**
- 推文发布后 15 分钟内评论（X 算法黄金窗口）
- 账号需要有真实互动历史（新账号进前排概率极低）
- 评论前两行必须有价值（折叠前可见）

**高互动评论结构**
```
[相关数据/观点] + [个人见解] + [引导互动的问题]
```

**示例**
- 差的评论："Check out our trading bot! Link in bio"
- 好的评论："This fee structure mirrors what Coinbase did in Q3 2024 — that move drove a 40% volume increase. Are you targeting the same institutional segment here?"

**避免 Spam 判定**
- 每天评论不超过 50 条（新账号 <20 条）
- 评论间隔不少于 5 分钟
- 不在同一推文下发多条评论
- 混合点赞、转发、评论等不同互动类型

#### 风险控制

**重大政策限制（2026.2）**
- X 平台已限制通过 API 发送的程序化回复
- 仅允许回复 @提及你或引用你的推文
- Enterprise 账户不受限制，但成本极高

**封号风险等级**
| 行为 | 风险 | 后果 |
|------|------|------|
| 使用第三方自动化工具批量评论 | 极高 | 永久封禁 |
| 短时间大量重复评论 | 高 | 临时封禁/影子封禁 |
| 通过 API 自动回复 | 高 | API 访问被撤销 |
| 人工快速评论（合理频率） | 低 | 无 |

#### 成本估算

**X API 按量付费（2026.2 起）**
- 读取推文：$0.005/条
- 发帖/回复：$0.010/次
- 监控 50 个账号，每天约 $10-50

**SocialData API（更经济）**
- 读取推文：$0.0002/条（是 X API 的 1/25）
- 监控 50 个账号，每天约 $2-10

**推荐方案**
- 使用 SocialData API 监控（成本低）
- 通过 twikit 发布评论（免费，但需控制频率）
- Telegram Bot 通知（免费）

#### 数据模型设计

```python
class MonitoredAccount(Base):
    id: int
    username: str              # Twitter 用户名
    user_id: str              # Twitter 用户 ID
    priority: int             # 优先级（1-3）
    poll_interval: int        # 轮询间隔（秒）
    last_tweet_id: str        # 最后一条推文 ID（用于增量获取）
    last_checked_at: datetime # 最后检查时间
    is_active: bool           # 是否启用监控

class MonitorNotification(Base):
    id: int
    account_id: int           # 关联的监控账号
    tweet_id: str             # 推文 ID
    tweet_text: str           # 推文内容
    tweet_url: str            # 推文链接
    author_name: str          # 作者名称
    created_at: datetime      # 推文发布时间
    notified_at: datetime     # 通知发送时间
    is_commented: bool        # 是否已评论
    comment_text: str         # 评论内容（如果已评论）
```

#### 前端界面设计

**账号监控管理页面**
- 监控账号列表（添加/删除/编辑）
- 优先级设置（1-3 级）
- 轮询间隔配置
- 启用/禁用开关

**推文通知列表**
- 实时显示新推文通知
- 推文内容预览
- 一键跳转到 Twitter
- AI 生成评论草稿（可选）
- 标记已评论状态

**数据统计**
- 监控账号数量
- 今日新推文数量
- 今日评论数量
- 评论互动数据（点赞/回复数）

#### 实施优先级

1. **Phase 1（1-2 天）**：监控层实现
   - MonitoredAccount 模型
   - twikit `get_user_tweets()` 轮询
   - 增量获取逻辑（since_id）

2. **Phase 2（1 天）**：通知层实现
   - Telegram Bot 集成
   - 推文通知推送
   - 通知历史记录

3. **Phase 3（2-3 天）**：前端界面
   - 账号管理页面
   - 通知列表页面
   - 数据统计看板

4. **Phase 4（可选）**：AI 辅助
   - 评论草稿生成
   - 评论质量评分
   - 最佳评论时机提示

#### 参考资料

- [X API 定价变化](https://pricetimeline.com/data/price/x-api)
- [X 限制 API 程序化回复（2026.2）](https://roboin.io/article/en/2026/02/24/x-limits-api-based-automated-replies-to-combat-engagement-farming/)
- [早期互动窗口策略](https://siftfeed.com/guides/early-engagement-windows-x)
- [Twitter 自动化安全指南 2026](https://www.contagent.ai/blog/twitter-automation-safe)
- [加密货币 KOL 列表](https://awisee.com/blog/top-crypto-x-accounts/)
- [SocialData API 定价](https://docs.socialdata.tools/getting-started/pricing)

### Phase 8: 内容策略优化 -- 计划中
> 目标：让自动生成的内容直接服务于 HAA 获客转化

- [ ] 围绕 HAA 教程内容设计专属 LLM 推文模板（教程拆解、功能亮点、收益展示）
- [ ] 内容比例策略：50% 教育内容 / 30% 互动内容 / 20% 产品推广
- [ ] 教育线程（Thread）自动生成：将教程步骤拆成 Twitter Thread
- [ ] 推文自动附带 HAA 教程链接，缩短转化路径
- [ ] A/B 测试：同一主题不同风格的推文对比效果

### Phase 9: 多账号与规模化 -- 远期计划
- [ ] 多 Twitter 账号管理
- [ ] 账号矩阵协同运营
- [ ] 跨账号内容去重
- [ ] 统一数据看板

---

## 优化方向与待办（v0.4.0 之后）

### 高优先级

**1. Engage 页面批量自动评论模式**
- 搜索关键词后，支持一键批量处理所有结果（AI 生成 + 自动发送）
- 每条之间随机延迟 30-120s，避免触发风控
- 复用现有 `/api/engage/generate-reply` + `/api/engage/reply/{id}` 接口
- 前端加进度条和实时状态展示

**2. Cookie 过期主动提示**
- 目前 cookie 失效后所有功能静默报错，用户无感知
- 在顶部状态栏加 cookie 健康检测，失效时显示醒目警告
- 后端定期调用 `client.user()` 检测，结果写入 `/api/cookies/status`

**3. 监控服务请求频率控制**
- monitor service 每 30s 轮询一次，多账号并发容易触发 Twitter 403
- 加全局请求队列，同一时间只允许一个 twikit 请求在飞
- 对 `TooManyRequests` 异常读取 `rate_limit_reset` 自动等待后重试

### 中优先级

**4. 推文内容模板库**
- 保存常用推文模板，支持变量替换（`{date}`、`{topic}`、`{price}`）
- 配合排期功能批量创建推文，减少重复操作

**5. 数据统计面板**
- 发推数量、回复数量、各关键词互动效果趋势图
- 数据已在库里，只需聚合展示

**6. 自动评论内容多样化**
- 当前 LLM prompt 固定，生成内容风格相似，容易被识别
- 加多套 prompt 模板随机切换，或支持用户自定义 prompt 风格

### 低优先级

**7. 操作结果通知**
- 自动互动成功/失败后推送微信或邮件通知

**8. 黑名单**
- 屏蔽特定用户，不对其推文做任何互动

**9. 多账号支持**
- 目前只支持单 Twitter 账号，改动面较大，放远期

---

## 运行方式

### 开发模式

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
pnpm install
pnpm dev
```

### Docker部署

```bash
docker-compose up -d --build
```

---

## API端点设计

### 推文管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tweets | 获取推文列表 |
| POST | /api/tweets | 创建推文 |
| GET | /api/tweets/{id} | 获取单条推文 |
| PUT | /api/tweets/{id} | 更新推文 |
| DELETE | /api/tweets/{id} | 删除推文 |
| POST | /api/tweets/{id}/publish | 立即发布 |
| POST | /api/tweets/{id}/schedule | 设置排期 |

### 素材管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/media | 获取素材列表 |
| POST | /api/media/upload | 上传素材 |
| DELETE | /api/media/{id} | 删除素材 |

### LLM生成
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/llm/generate | 生成推文内容 |
| GET | /api/llm/templates | 获取提示词模板 |

### 系统配置
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/settings | 获取配置（含已保存的Twitter用户名/邮箱） |
| PUT | /api/settings | 更新配置 |
| POST | /api/settings/twitter-login | 前端Twitter登录（保存凭证到数据库） |
| POST | /api/settings/test-twitter | 测试Twitter连接 |
| POST | /api/settings/test-llm | 测试LLM连接 |

---

## twikit 技术调研（2026.3）

项目核心依赖 twikit 库实现 Twitter 自动化操作。已升级到 v2.3.3，启用 `x_client_transaction` + `ui_metrics` 反检测模块。

### 当前使用情况

项目仅使用了 twikit 约 5% 的能力：`login()` + `create_tweet()` + `upload_media()`。

### twikit 完整能力清单

#### 认证与会话

| 方法 | 说明 | 项目状态 |
|------|------|---------|
| `login(auth_info_1, auth_info_2, password, totp_secret)` | 登录（支持2FA） | 已实现 |
| `save_cookies(path)` / `load_cookies(path)` | Cookie 持久化 | 已实现 |
| `set_delegate_account(user_id)` | 代理账号操作 | 未使用 |
| `unlock()` | 解锁被锁定账号（需 captcha_solver） | 未使用 |

#### 推文操作

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `create_tweet(text, media_ids, reply_to, ...)` | 发布推文 | - | 已实现 |
| `get_tweet_by_id(tweet_id)` | 获取推文详情+互动数据 | 简单 | 效果追踪核心 |
| `delete_tweet(tweet_id)` | 删除推文 | 简单 | 内容管理 |
| `favorite_tweet(tweet_id)` | 点赞 | 简单 | 互动自动化 |
| `unfavorite_tweet(tweet_id)` | 取消点赞 | 简单 | 互动自动化 |
| `retweet(tweet_id)` | 转推 | 简单 | 互动自动化 |
| `delete_retweet(tweet_id)` | 取消转推 | 简单 | 互动自动化 |
| `bookmark_tweet(tweet_id, folder_id)` | 收藏 | 简单 | 内容管理 |
| `create_scheduled_tweet(scheduled_at, text)` | Twitter原生定时推文 | 简单 | 备选排期方案 |
| `get_retweeters(tweet_id)` | 获取转推者列表 | 简单 | 用户分析 |
| `get_favoriters(tweet_id)` | 获取点赞者列表 | 简单 | 用户分析 |

#### 搜索

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `search_tweet(query, product, count)` | 搜索推文（Top/Latest/Media） | 简单 | 关键词监控核心 |
| `search_user(query, count)` | 搜索用户 | 简单 | 目标用户发现 |

#### 用户操作

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `get_user_by_screen_name(name)` | 通过用户名获取用户 | 简单 | 竞品分析 |
| `get_user_by_id(user_id)` | 通过ID获取用户 | 简单 | 用户信息 |
| `follow_user(user_id)` | 关注 | 简单 | 互动自动化 |
| `unfollow_user(user_id)` | 取消关注 | 简单 | 互动自动化 |
| `get_user_followers(user_id)` | 获取粉丝列表 | 简单 | 竞品粉丝分析 |
| `get_user_following(user_id)` | 获取关注列表 | 简单 | 用户分析 |
| `get_user_tweets(user_id, tweet_type)` | 获取用户推文 | 简单 | 竞品内容分析 |
| `get_latest_followers(user_id)` | 获取最新粉丝（max 200） | 简单 | 粉丝增长追踪 |
| `block_user()` / `mute_user()` | 拉黑/静音 | 简单 | 账号安全 |

#### 时间线与通知

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `get_timeline()` / `get_latest_timeline()` | 获取推荐/最新时间线 | 简单 | 内容发现 |
| `get_notifications(type)` | 获取通知（All/Verified/Mentions） | 简单 | 监控@提及，合规自动回复 |

#### 趋势话题

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `get_trends(category)` | 获取趋势（trending/for-you/news等） | 简单 | 蹭热点话题 |
| `get_place_trends(woeid)` | 获取特定地区趋势 | 简单 | 区域化运营 |

#### 私信

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `send_dm(user_id, text)` | 发送私信 | 简单 | 高风险，不建议自动化 |
| `get_dm_history(user_id)` | 获取私信历史 | 简单 | 用户沟通记录 |

#### 列表管理

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `create_list(name)` / `add_list_member()` | 创建和管理列表 | 中等 | 组织目标用户群 |
| `get_list_tweets(list_id)` | 获取列表推文 | 简单 | 监控目标用户动态 |

#### 社区

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `search_community(query)` | 搜索社区 | 简单 | 发现加密社区 |
| `get_community_tweets(community_id)` | 获取社区推文 | 简单 | 社区内容监控 |
| `join_community(community_id)` | 加入社区 | 简单 | 精准用户触达 |

#### 投票与媒体

| 方法 | 说明 | 难度 | 用途 |
|------|------|------|------|
| `create_poll(choices, duration)` | 创建投票 | 简单 | 高互动率内容 |
| `upload_media(source)` | 上传媒体 | - | 已实现 |
| `create_media_metadata(media_id, alt_text)` | 设置媒体alt文本 | 简单 | 无障碍支持 |

### Tweet 对象关键属性

```
id                  - 推文ID
text / full_text    - 推文内容
user                - 作者 (User对象)
created_at_datetime - 创建时间
favorite_count      - 点赞数 (int)
retweet_count       - 转推数 (int)
reply_count         - 回复数 (int)
quote_count         - 引用数 (int)
view_count          - 浏览量 (str)
favorited           - 当前用户是否已点赞 (bool)
hashtags            - 话题标签 (list)
media               - 媒体列表
urls                - 链接列表
in_reply_to         - 回复的推文ID
is_quote_status     - 是否引用推文
```

### User 对象关键属性

```
id                  - 用户ID
name / screen_name  - 显示名 / 用户名
description         - 个人简介
followers_count     - 粉丝数
following_count     - 关注数
statuses_count      - 推文数
is_blue_verified    - 是否蓝V
protected           - 是否私密账号
can_dm              - 是否可私信
```

### 错误处理体系

```
TwitterException (基类)
  +-- BadRequest (400)
  +-- Unauthorized (401)
  +-- Forbidden (403)
  +-- NotFound (404)
  +-- TooManyRequests (429) -- 含 rate_limit_reset 时间戳
  +-- ServerError (5xx)
  +-- CouldNotTweet
  |     +-- DuplicateTweet (187)
  +-- AccountLocked (326, 需Arkose验证)
  +-- AccountSuspended (37, 64)
  +-- InvalidMedia (324)
```

`TooManyRequests` 的 `rate_limit_reset` 属性可用于实现智能等待重试。

### 版本升级记录（v1.7.6 -> v2.3.3，已完成 2026.3.9）

v2.0 有破坏性变更，以下已全部适配：
- 移除同步版本，仅保留异步 Client
- 新增依赖：lxml, webvtt-py, m3u8, Js2Py-3.13（httpx 改为 httpx[socks]）
- `login()` 返回值从 None 改为 dict（包含登录状态信息）
- `login()` 新增 `cookies_file` 参数，可直接在登录时指定 cookie 保存路径
- `login()` 新增 `enable_ui_metrics` 参数（默认 True），用于模拟浏览器行为降低风控
- `upload_media()` 新增 `wait_for_completion`、`is_long_video` 等参数
- v2.x 新增 `x_client_transaction` 模块：自动生成 X-Client-Transaction-Id 请求头，模拟真实浏览器行为，这是 v2 最重要的反检测升级
- v2.x 新增 `ui_metrics` 模块：模拟 DOM 操作生成 ui_metrics 数据，进一步降低被检测概率
- 当前项目代码已使用 async/await，升级后兼容性良好
- 已完成升级，`login()` 启用 `cookies_file` + `enable_ui_metrics=True`

### 实现难度评估

| 功能模块 | 涉及的 twikit 方法 | 难度 | 预估工时 |
|---------|-------------------|------|---------|
| 推文互动数据获取 | `get_tweet_by_id` | 简单 | 1-2h |
| 关键词搜索监控 | `search_tweet` | 简单 | 2-3h |
| 自动点赞/转推 | `favorite_tweet` / `retweet` | 简单 | 每个10min |
| 自动关注/取关 | `follow_user` / `unfollow_user` | 简单 | 每个10min |
| 用户/粉丝数据获取 | `get_user_*` 系列 | 简单 | 2-3h |
| 通知监控（@提及） | `get_notifications` | 简单 | 1h |
| 趋势话题获取 | `get_trends` | 简单 | 1h |
| 频率控制+安全防护 | 自建逻辑 | 中等 | 2-3天 |
| 数据存储+定时任务 | 自建逻辑 | 中等 | 1-2天 |
| 前端管理界面 | 自建逻辑 | 中等 | 2-3天 |

twikit API 调用层封装约半天，主要工作量在频率控制、数据存储和前端界面。

---

## twikit 踩坑细节与实操建议（2026.3）

### 已知高频问题

**1. 登录 400 错误："LoginFlow is currently not accessible"**
- 原因：Twitter 服务端临时限制、IP 被标记、或 cookie 文件损坏
- 解决：删除旧 cookie 文件重新登录；换 IP/代理；等待几小时后重试；确保 twikit 是最新版本
- 预防：不要频繁调用 `login()`，cookie 有效时直接复用

**2. "This request looks like it might be automated"（CouldNotTweet）**
- 触发条件：短时间内大量相似操作、内容重复度高、操作模式过于规律（固定间隔）
- 应对：操作间隔随机化（不是固定 sleep）、内容多样化、模拟人类作息时间（8:00-23:00）

**3. AccountLocked（Arkose 验证码）**
- twikit 2.x 内置 `Capsolver` 类，支持自动解锁
- 接入方式：注册 [capsolver.com](https://capsolver.com) 获取 API key，初始化时传入 `captcha_solver=Capsolver(api_key='...')`
- 预防比治疗重要：严格控制频率是避免触发 Arkose 的关键

**4. Cookie 过期**
- Twitter cookie 有效期不固定（几天到几周）
- 建议：每次操作前捕获 `Unauthorized` 异常，失败时自动重新登录并保存新 cookie
- twikit 2.x `login()` 支持 `cookies_file` 参数，可自动保存

**5. TooManyRequests 智能重试**
```python
from twikit.errors import TooManyRequests
import asyncio, time

try:
    await client.create_tweet(text)
except TooManyRequests as e:
    if e.rate_limit_reset:
        wait = e.rate_limit_reset - time.time() + 5  # 多等5秒缓冲
        await asyncio.sleep(max(wait, 0))
        # 重试
```

### X 平台 2026 年新政策

| 政策 | 生效时间 | 影响 |
|------|---------|------|
| API 自动回复限制 | 2026.2 | 仅允许回复 @提及你的推文；twikit 模式需极度谨慎控制频率 |
| 付费推广标注 | 2026.3.1 | 商业推广内容必须明确标注；自有账号运营推广 HAA 需注意措辞 |
| Grok 算法升级 | 持续 | 从"计数行为"转向"理解内容"，语义相关性比粉丝数更重要 |
| 反爬升级 | 持续 | 设备指纹检测 + 行为分析 + IP 检测，v2.x 的 x_client_transaction 模块已应对 |

### 安全操作频率（综合社区数据）

| 操作 | 安全日限 | 保守建议（新账号） | 备注 |
|------|---------|-----------------|------|
| 发推（含回复/引用） | 20-30 | 10-15 | - |
| 点赞 | 50-80 | 30-50 | 最安全的互动方式 |
| 关注 | 20-30 | 10-20 | 新账号建议 <10 |
| 取关 | 20-30 | 10-20 | 不要同天大量关注又取关 |
| 转推 | 20-30 | 10-15 | - |
| 搜索 | 无明确限制 | 每分钟 1-2 次 | 注意 TooManyRequests |
| 私信 | 极高风险 | 不建议自动化 | 容易直接封号 |

**关键原则：**
- 操作间隔随机化（30s-5min），绝对不要固定间隔
- 模拟人类作息：活跃时段 8:00-23:00，凌晨不操作
- 不同类型操作之间也要有间隔，不要连续执行
- 新账号前 2 周操作量减半

### twikit v2.x 反检测机制（重要）

v2.x 新增两个关键模块，显著降低被检测概率：

1. **x_client_transaction**：自动生成 `X-Client-Transaction-Id` 请求头，通过解析 Twitter 首页 JS 动态计算，模拟真实浏览器行为
2. **ui_metrics**：模拟 DOM 操作生成 `ui_metrics` 数据，在登录时传递给 Twitter 服务端

这是升级到 v2.x 最重要的理由，v1.x 缺少这两个模块，在 2026 年的 X 反爬策略下风险更高。

---

## HAA 产品信息（推文内容参考）

> 本节用于指导 LLM 生成推文内容，确保内容准确反映 HAA 的核心价值。

### 产品定位

HAA (Hyper Alpha Arena) 是一个 AI 驱动的加密货币自主交易平台，让用户可以用 AI 模型（GPT-5、Claude、Deepseek）在 Hyperliquid 和 Binance Futures 上自动交易永续合约。

- 官网：[akooi.com](https://www.akooi.com/)
- 教程：[Getting Started](https://www.akooi.com/docs/zh/guide/getting-started.html)
- 本地访问：`localhost:8802`

### 核心卖点（推文素材）

| 卖点 | 说明 | 推文角度 |
|------|------|---------|
| 真实资金自主交易 | AI 模型用真实资金交易永续合约，非模拟盘 | "让 AI 帮你交易，你只需设置策略" |
| 多 AI 模型支持 | GPT-5、Claude、Deepseek 可选 | "哪个 AI 模型最会炒币？" |
| 可定制 Prompt | 用户可自定义交易策略提示词 | "用自然语言写交易策略" |
| 完整风险管理 | 内置风控系统，保护本金 | "AI 交易也能控制风险" |
| 双交易所支持 | Hyperliquid（DEX）+ Binance Futures（CEX） | "DEX + CEX 双线布局" |
| 灵感来源 Alpha Arena | 受 nof1 Alpha Arena 启发，经过真实验证 | "DeepSeek 在 Alpha Arena 中击败 GPT-5" |

### 内容策略建议

参考 Alpha Arena 实验（6 个 AI 模型各持 $10,000 真实资金在 Hyperliquid 交易）的热度，HAA 的推文可以围绕：

1. **教育内容（50%）**：AI 交易原理、Hyperliquid 介绍、永续合约基础、风险管理
2. **互动内容（30%）**：投票（哪个 AI 模型最强？）、问答、社区讨论
3. **产品推广（20%）**：功能演示、用户收益展示、教程链接

---

## 注意事项

1. **Twitter API 限制**：Free Tier 每月 500 条推文且几乎无法读取数据，Basic $200/月可获取 public_metrics
2. **twikit 模式风险**：非官方库，本质是爬虫行为，需严格控制操作频率避免封号；v2.x 反检测能力显著强于 v1.x
3. **自动回复限制**：2026.2 起 X 平台限制 API 自动回复，仅允许回复 @提及你的推文；twikit 模式同样需谨慎
4. **安全操作频率**：关注 20-30 次/天，点赞 50-80 次/天，推文 20-30 条/天，操作间隔随机化（详见踩坑章节）
5. **LLM 成本**：生成内容会消耗 API 调用额度，注意监控用量
6. **素材限制**：Twitter 对图片/视频有格式和大小限制（当前限制 10MB）
7. **付费推广标注**：2026.3.1 起 X 要求所有付费推广内容必须明确标注；自有账号推广 HAA 需注意措辞
8. **版本说明**：已升级到 twikit 2.3.3，v2.x 反检测模块（x_client_transaction + ui_metrics）已启用

---

## License

MIT License
