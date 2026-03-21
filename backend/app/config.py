from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Twitter 账号配置 (twikit)
    twitter_username: str = ""
    twitter_email: str = ""
    twitter_password: str = ""
    twitter_publish_mode: str = "twikit"

    # LLM配置
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"

    # 代理配置（留空则不使用代理）
    proxy_url: str = ""

    # 服务配置
    backend_port: int = 8000
    frontend_port: int = 3000

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./data/haa.db"

    # 上传配置
    upload_dir: str = "./uploads"
    max_upload_size: int = 104857600  # 100MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# 确保必要目录存在
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs("./data", exist_ok=True)
