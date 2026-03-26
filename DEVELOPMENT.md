# Development Guide

This document is the single source of truth for what has been implemented.
Before adding any feature, check here first to avoid duplicating or breaking existing work.

---

## Implemented Features

### Pages & Routes

| Page | Route | File | Status |
|------|-------|------|--------|
| Tweet Management | `/` -> redirect to `/tweets` | `frontend/src/pages/Tweets.tsx` | Done |
| Schedule Calendar | `/calendar` | `frontend/src/pages/Calendar.tsx` | Done |
| Media Library | `/media` | `frontend/src/pages/Media.tsx` | Done |
| Engage (search & reply) | `/engage` | `frontend/src/pages/Engage.tsx` | Done |
| Account Monitor | `/monitor` | `frontend/src/pages/Monitor.tsx` | Done |
| Conversations | `/conversations` | `frontend/src/pages/Conversations.tsx` | Done |
| Settings | `/settings` | `frontend/src/pages/Settings.tsx` | Done |

All routes are registered in `frontend/src/App.tsx`.
All nav items are registered in `frontend/src/components/Sidebar.tsx`.

**When adding a new page, update BOTH files.**

---

### Backend API Endpoints

#### Tweets — `backend/app/routers/tweets.py`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tweets` | List tweets |
| POST | `/api/tweets` | Create tweet |
| GET | `/api/tweets/{id}` | Get tweet |
| PUT | `/api/tweets/{id}` | Update tweet |
| DELETE | `/api/tweets/{id}` | Delete tweet |
| POST | `/api/tweets/{id}/publish` | Publish immediately |
| POST | `/api/tweets/{id}/schedule` | Schedule tweet |

#### Media — `backend/app/routers/media.py`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/media` | List media |
| POST | `/api/media/upload` | Upload file |
| DELETE | `/api/media/{id}` | Delete media |

#### Settings — `backend/app/routers/settings.py`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | Get settings (username/email returned, password masked) |
| PUT | `/api/settings` | Update settings |
| POST | `/api/settings/twitter-login` | Login with credentials, saves cookie |
| POST | `/api/settings/test-twitter` | Test Twitter connection |
| POST | `/api/settings/test-llm` | Test LLM connection |

#### LLM — `backend/app/routers/llm.py`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/llm/generate` | Generate tweet content |
| GET | `/api/llm/templates` | Get prompt templates |

#### Engage — `backend/app/routers/engage.py`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/engage/search` | Search tweets by keyword |
| GET | `/api/engage/replied-ids` | Get all tweet IDs already replied to |
| POST | `/api/engage/generate-reply` | Generate AI reply/quote draft |
| POST | `/api/engage/reply/{tweet_id}` | Post reply, records to DB to prevent duplicates |

`generate-reply` accepts `mode: "reply" | "quote"` (default `"reply"`).
`reply/{tweet_id}` accepts optional `tweet_text` and `author_username` for record-keeping.

#### Monitor — `backend/app/routers/monitor.py`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/monitor/accounts` | List monitored accounts |
| POST | `/api/monitor/accounts` | Add account to monitor |
| PUT | `/api/monitor/accounts/{id}` | Update account config |
| DELETE | `/api/monitor/accounts/{id}` | Remove account |
| GET | `/api/monitor/notifications` | List new tweet notifications |
| POST | `/api/monitor/notifications/{id}/reply` | Post reply to a notification tweet |
| POST | `/api/monitor/notifications/{id}/quote` | Post quote tweet |
| POST | `/api/monitor/notifications/{id}/retweet` | Retweet |
| POST | `/api/monitor/notifications/{id}/mark-read` | Mark notification as read |

#### Logs — `backend/app/routers/logs.py`
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/logs` | Get operation logs |

#### Cookies — `backend/app/routers/cookies.py`
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/cookies/upload` | Upload twitter_cookies.json directly |
| GET | `/api/cookies/status` | Check cookie file status |

---

### Database Tables

All tables are auto-created on startup via `init_db()` in `backend/app/database.py`.
SQLite file: `backend/data/app.db`

| Table | Model file | Description |
|-------|-----------|-------------|
| `tweets` | `models/tweet.py` | Scheduled/published tweets |
| `media` | `models/media.py` | Uploaded media files |
| `tweet_media` | `models/tweet.py` | Many-to-many join table |
| `settings` | `models/setting.py` | App config (LLM keys, Twitter credentials) |
| `monitored_accounts` | `models/monitor.py` | Accounts being monitored |
| `monitor_notifications` | `models/monitor.py` | New tweet notifications from monitored accounts |
| `engage_replies` | `models/engage.py` | Record of tweets replied to via Engage page (dedup) |

**When adding a new model, register it in `backend/app/models/__init__.py` so it gets picked up by `create_all`.**

---

### Services

| File | Role |
|------|------|
| `services/twitter_api.py` | Unified Twitter facade — all routers call this, never engine implementations directly |
| `services/twitter_twikit.py` | twikit implementation (login, tweet, reply, search, retweet, etc.) |
| `services/twitter_browser.py` | browser-mode implementation and richer read/write error classification |
| `services/twitter_risk_control.py` | per-account risk state, cooldown and UI-facing warnings |
| `services/twitter_auth_backoff.py` | auth retry/backoff helpers shared by login flows |
| `services/llm_service.py` | OpenAI-compatible LLM content generation |
| `services/scheduler.py` | APScheduler — runs scheduled tweet publishing and monitor polling |
| `services/monitor_service.py` | Monitor polling logic — calls `get_user_tweets()` via twikit |

Twitter auth/engine mode is controlled centrally in `twitter_api.py` and exposed through Settings APIs.

---

### Key Config

Environment variables (`.env` file):

```
TWITTER_USERNAME=
TWITTER_EMAIL=
TWITTER_PASSWORD=
PROXY_URL=http://host.docker.internal:7896
LLM_API_BASE=
LLM_API_KEY=
LLM_MODEL=
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

Twitter credentials can also be set via the Settings page UI — they are stored in the `settings` table and take priority over `.env`.

---

## Checklist When Adding a New Page

1. Create `frontend/src/pages/NewPage.tsx`
2. Add route in `frontend/src/App.tsx`
3. Add nav item in `frontend/src/components/Sidebar.tsx`
4. If new backend endpoints needed, create `backend/app/routers/new.py`
5. Register router in `backend/app/routers/__init__.py` and `backend/app/main.py`
6. If new DB table needed, create `backend/app/models/new.py` and register in `backend/app/models/__init__.py`
7. Update this file

## Checklist When Adding a New DB Model

1. Create model in `backend/app/models/new.py` inheriting from `Base`
2. Import it in `backend/app/models/__init__.py`
3. Rebuild the backend Docker image (`docker compose build backend`)
4. Table will be created automatically on next startup
5. Update the table list in this file

---

## Docker Update Commands

```bash
# Full rebuild (after code changes)
cd /home/wwwroot/HAA-Social-Autopilot
HTTP_PROXY= HTTPS_PROXY= http_proxy= https_proxy= ALL_PROXY= \
  docker compose build --build-arg HTTP_PROXY=http://172.17.0.1:7896 \
                       --build-arg HTTPS_PROXY=http://172.17.0.1:7896 backend frontend
docker compose up -d

# Backend only
docker compose build backend && docker compose up -d backend

# Frontend only
docker compose build frontend && docker compose up -d frontend

# View logs
docker compose logs backend -f
docker compose logs frontend -f
```

## Verification Commands

```bash
cd /home/wwwroot/HAA-Social-Autopilot
make frontend-lint
make frontend-build
make backend-compile
make backend-test-docker
make check
```

If the host `python3` is lower than 3.10, treat `make backend-test-docker` as the source of truth for backend test results.
