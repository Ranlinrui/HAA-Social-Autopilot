from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Twitter 账号配置 (twikit/browser)
    twitter_username: str = ""
    twitter_email: str = ""
    twitter_password: str = ""
    twitter_publish_mode: str = "twikit"

    # BrowserEngine 配置
    browser_headless: bool = True
    browser_executable_path: str = "/usr/bin/chromium"
    browser_timeout_ms: int = 90000
    browser_low_traffic_mode: bool = True
    browser_block_images: bool = True
    browser_block_media: bool = True
    browser_block_fonts: bool = True
    browser_mentions_reply_resolution_limit: int = 2
    browser_health_check_search_count: int = 1
    browser_health_check_mentions_count: int = 1

    # LLM配置
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"

    # 代理配置（留空则不使用代理）
    proxy_url: str = ""

    # 省流量模式配置
    low_traffic_mode: bool = True
    monitor_loop_interval_seconds: int = 120
    monitor_priority_high_interval_seconds: int = 180
    monitor_priority_medium_interval_seconds: int = 600
    monitor_priority_low_interval_seconds: int = 1800
    monitor_timeline_fetch_count: int = 3
    conversation_default_poll_interval_seconds: int = 600
    conversation_mentions_fetch_count: int = 20
    auto_action_min_interval_seconds: int = 240
    auto_reply_hourly_limit: int = 4
    auto_retweet_hourly_limit: int = 2
    auto_action_daily_limit: int = 12
    auto_engage_skip_ratio_single_account: float = 0.45
    auto_engage_skip_ratio_multi_account: float = 0.2
    auto_engage_high_load_skip_ratio: float = 0.7
    auto_engage_high_load_threshold_24h: int = 8

    # 服务配置
    backend_port: int = 8000
    frontend_port: int = 3000
    backend_vnc_port: int = 6080

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/haa.db"

    # 上传配置
    upload_dir: str = "./uploads"
    max_upload_size: int = 104857600  # 100MB

settings = Settings()

# 确保必要目录存在
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs("./data", exist_ok=True)
