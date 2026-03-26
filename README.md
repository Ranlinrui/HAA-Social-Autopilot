# HAA Social Autopilot

**Twitter/X Social Media Automation & Growth Tool**

A lightweight, self-hosted automation platform for organic Twitter/X growth. Schedule posts, monitor target accounts, engage with relevant conversations, and track follow-up threads — all powered by an LLM of your choice.

---

## Features

- **Tweet Scheduling** — Create, edit, and schedule tweets with a visual calendar
- **Media Library** — Upload and manage images/videos; attach up to 4 images when creating a tweet
- **LLM Content Generation** — 5 content-specific prompt templates (AI reasoning showcase, trade report, AI vs AI comparison, hot take, story/narrative); generate tweets and replies using any OpenAI-compatible API
- **Engage** — Search hot tweets by keyword, generate contextual AI replies, batch reply with rate-limit protection; quote-tweet with optional image attachments (up to 4)
- **Account Monitoring** — Watch target accounts for new tweets, auto-engage with configurable delay
- **Conversation Follow-up** — Detect replies to your comments, continue threads in auto or manual mode
- **Multi-mode Twitter Auth** — Twikit, cookie, and browser modes behind a unified backend facade
- **Risk-aware UI Guards** — Account-scoped risk banners and guarded actions for safer retries

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Web App                               │
│              React + TailwindCSS + shadcn/ui                │
├─────────────────────────────────────────────────────────────┤
│  - Tweet management (create / edit / delete / schedule)     │
│  - Publishing calendar                                      │
│  - Media library                                            │
│  - Engage (search + reply + batch)                          │
│  - Monitor (account watching + auto-engage)                 │
│  - Conversations (follow-up thread management)              │
│  - Settings (Twitter auth mode / login / LLM config)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                              │
│                FastAPI + SQLite + APScheduler               │
├─────────────────────────────────────────────────────────────┤
│  - RESTful API (tweet CRUD / media / settings)              │
│  - Twitter engine facade (twikit / cookie / browser)        │
│  - LLM content generation (OpenAI-compatible)               │
│  - Scheduler (APScheduler for timed publishing)             │
│  - Conversation service (mention polling + thread tracking) │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Component | Choice | Notes |
|-----------|--------|-------|
| Web framework | FastAPI | Async Python |
| Database | SQLite | Zero-config, single file |
| ORM | SQLAlchemy | Async support |
| Scheduler | APScheduler | Cron-style task scheduling |
| Twitter engine | twikit + browser fallback | Unified facade, no official API key required |
| LLM client | openai | OpenAI-compatible interface |

### Frontend
| Component | Choice | Notes |
|-----------|--------|-------|
| Framework | React 18 | |
| Build tool | Vite | Fast dev/build |
| Styling | TailwindCSS | Utility-first CSS |
| UI components | shadcn/ui | Accessible component library |
| State | Zustand | Lightweight store |
| Calendar | react-big-calendar | Scheduling view |
| HTTP | axios | API requests |

---

## Directory Structure

```
HAA-Social-Autopilot/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # configuration management
│   │   ├── database.py             # SQLite connection
│   │   ├── logger.py               # logging setup
│   │   ├── models/
│   │   │   ├── tweet.py
│   │   │   ├── media.py
│   │   │   ├── setting.py
│   │   │   ├── monitor.py          # MonitoredAccount / MonitorNotification
│   │   │   ├── engage.py           # EngageReply
│   │   │   └── conversation.py     # ConversationThread / ConversationSetting
│   │   ├── routers/
│   │   │   ├── tweets.py
│   │   │   ├── media.py
│   │   │   ├── settings.py
│   │   │   ├── llm.py
│   │   │   ├── engage.py
│   │   │   ├── monitor.py
│   │   │   ├── conversation.py
│   │   │   ├── logs.py
│   │   │   └── cookies.py
│   │   └── services/
│   │       ├── twitter_api.py      # unified Twitter facade
│   │       ├── twitter_twikit.py   # twikit v2.3.3 engine
│   │       ├── monitor_service.py  # account polling + auto-engage
│   │       ├── conversation_service.py  # mention polling + thread management
│   │       ├── llm_service.py      # LLM content generation
│   │       └── scheduler.py        # APScheduler tasks
│   ├── uploads/
│   ├── data/                       # SQLite DB + twitter_cookies.json
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Tweets.tsx
│   │   │   ├── Calendar.tsx
│   │   │   ├── Media.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── Engage.tsx
│   │   │   ├── Monitor.tsx
│   │   │   └── Conversations.tsx
│   │   ├── stores/index.ts
│   │   ├── services/api.ts
│   │   └── types/index.ts
│   ├── nginx.conf
│   └── package.json
├── Makefile
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# Twitter credentials (can also be set via the Settings page in the UI)
TWITTER_USERNAME=your_username
TWITTER_EMAIL=your_email@example.com
TWITTER_PASSWORD=your_password

# LLM configuration (any OpenAI-compatible endpoint)
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your_api_key
LLM_MODEL=gpt-4o

# Service ports
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### LLM Prompt Customization

The engage, monitor, and conversation services all use configurable prompts. You can customize the AI persona and product promotion behavior via the Settings page:

| Setting key | Description |
|-------------|-------------|
| `product_name` | Full product name used in generated replies |
| `product_url` | Product URL for reference |
| `product_desc` | One-line product description |
| `persona_zh` | Chinese persona for the AI author |
| `persona_en` | English persona for the AI author |
| `promo_topics` | Comma-separated Chinese trigger topics for product mentions |
| `promo_topics_en` | Comma-separated English trigger topics |

---

## Running

### Docker (recommended)

```bash
docker-compose up -d --build
```

### Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Verification

The backend requires **Python 3.10+**. The host `python3` on some machines may be older, so Docker-based verification is the safest baseline.

```bash
# Frontend checks
make frontend-lint
make frontend-build

# Backend syntax check
make backend-compile

# Backend tests in a clean Python 3.12 container
make backend-test-docker

# Run all checks
make check
```

`make backend-test-docker` is the canonical test path when local Python does not satisfy the project requirement.

---

## Key Modules

### Engage
Search Twitter for relevant tweets by keyword, generate contextual AI replies, and send them individually or in batch. Batch mode includes:
- Configurable delay between replies (default 45-90s)
- Mandatory rest every 4 replies (3-5 min)
- Rate-limit circuit breaker: pauses 15 min on first 226 error, aborts batch on second

### Account Monitor
Watch a list of Twitter accounts for new tweets. When `auto_engage` is enabled, new tweets are automatically replied to or retweeted after a human-like random delay.

### Conversation Follow-up
Polls Twitter mention notifications to detect when someone replies to your comments. Supports:
- **Auto mode**: pre-generates a draft reply, sends after a configurable delay
- **Manual mode**: queues the thread for human review and one-click reply
- Multi-turn conversation history maintained per thread

---

## Rate Limit Guidelines

| Action | Safe daily limit | Conservative (new account) |
|--------|-----------------|---------------------------|
| Tweets (incl. replies) | 20-30 | 10-15 |
| Likes | 50-80 | 30-50 |
| Follows | 20-30 | 10-20 |
| Retweets | 20-30 | 10-15 |

Always randomize intervals (30s-5min). Never use fixed delays.

---

## Notes

- The default landing page is now `/tweets`; the old Dashboard page has been removed.
- Frontend checks are run with `npm`, not `pnpm`.
- Browser mode is still under active implementation; Twikit mode remains the primary production path.

---

## License

MIT License
