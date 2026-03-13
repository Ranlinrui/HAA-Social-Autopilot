# Changelog

All notable changes to HAA Social Autopilot will be documented in this file.

Format: `[version] - date` / `Added` / `Fixed` / `Changed`

---

## [0.4.0] - 2026-03-13

### Fixed
- Twitter auth 401/403: cookie file contained metadata fields (`account_name`, `updated_at`, `expires_at`) that were being injected as HTTP cookies — now only `auth_token` and `ct0` are passed to twikit
- In-memory twikit client not reloading after cookie update via UI — now resets automatically on `POST /api/cookies/update`
- Scheduler greenlet error when accessing lazy-loaded `media_items` outside async session — fixed with `selectinload`
- `UNIQUE constraint failed: engage_replies.tweet_id` when replying to the same tweet twice — insert is now idempotent
- Media images not displaying — URL path used `slice(-2)` missing the year directory, fixed to `slice(-3)`

### Added
- `reset_twitter_client()` to `twitter_api` facade

---

## [0.3.0] - 2026-03-10

### Added
- Account monitoring: add/remove/prioritize Twitter accounts to watch
- Auto-engage: automatically reply, retweet, or both when monitored accounts post
- Human-like random delay for auto-engage (triangular distribution + gaussian noise + 15% distraction pause, clamped 30–600s)
- Per-account auto-engage config: toggle, action type (reply/retweet/both), base delay
- Monitor service auto-starts on app startup via FastAPI lifespan hook
- Notification list with auto-engage status badges
- Manual comment/mark on notifications
- Quote tweet button on Engage page

---

## [0.2.0] - 2026-03-08

### Added
- Twitter cookie management UI (auth_token + ct0)
- Engage page: search tweets by keyword, AI-generated reply drafts, send reply, quote tweet
- Preset search queries for common topics
- Replied-before tracking to avoid duplicate replies
- LLM reply generation with HAA product context (Chinese + English)

### Changed
- Improved Twitter login flow with detailed error messages per error code
- Optimized twikit client initialization and retry logic

---

## [0.1.0] - 2026-03-01

### Added
- Initial project scaffold: FastAPI backend + React/Vite frontend + Docker Compose
- Tweet CRUD: create, list, delete drafts
- Immediate tweet publishing
- Scheduled tweet publishing with APScheduler (1-min interval check)
- Failed tweet retry (up to 3 times, 15-min interval)
- Media upload and library management
- LLM content generation (OpenAI-compatible API)
- Settings page: Twitter credentials, LLM config, proxy
- Operation logs viewer
- SQLite database with async SQLAlchemy
