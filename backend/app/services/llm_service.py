from openai import AsyncOpenAI
from typing import Optional, Tuple
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.setting import Setting
import logging

logger = logging.getLogger(__name__)


async def get_llm_config(db: Optional[AsyncSession] = None) -> dict:
    """Get LLM configuration from database or fallback to env"""
    config = {
        "api_key": settings.llm_api_key,
        "api_base": settings.llm_api_base,
        "model": settings.llm_model,
    }

    if db:
        result = await db.execute(select(Setting))
        db_settings = {s.key: s.value for s in result.scalars().all()}

        if "llm_api_key" in db_settings and db_settings["llm_api_key"]:
            config["api_key"] = db_settings["llm_api_key"]
        if "llm_api_base" in db_settings and db_settings["llm_api_base"]:
            config["api_base"] = db_settings["llm_api_base"]
        if "llm_model" in db_settings and db_settings["llm_model"]:
            config["model"] = db_settings["llm_model"]

    return config


async def get_product_config() -> dict:
    """
    Load product/persona promotion config from the database.
    Falls back to sensible defaults so the tool works out of the box.
    Keys stored in the settings table:
      product_name   - full product name, e.g. "Acme Analytics"
      product_url    - product URL, e.g. "acme.io"
      product_desc   - one-line description used in prompts
      persona_zh     - Chinese persona description for the AI author
      persona_en     - English persona description for the AI author
      promo_topics   - comma-separated trigger topics (zh), e.g. "爆仓,风控,回测"
      promo_topics_en - comma-separated trigger topics (en), e.g. "liquidation,backtesting"
    """
    from app.database import get_db
    try:
        async for db in get_db():
            result = await db.execute(select(Setting))
            db_settings = {s.key: s.value for s in result.scalars().all()}
            break
    except Exception:
        db_settings = {}

    return {
        "product_name": db_settings.get("product_name") or "Your Product",
        "product_url": db_settings.get("product_url") or "",
        "product_desc": db_settings.get("product_desc") or "",
        "persona_zh": db_settings.get("persona_zh") or "在 Twitter 上活跃的用户，有自己的经历和观点，偶尔会提到自己用过的工具",
        "persona_en": db_settings.get("persona_en") or "an active Twitter user with your own opinions, occasionally mention tools you've used",
        "promo_topics": db_settings.get("promo_topics") or "",
        "promo_topics_en": db_settings.get("promo_topics_en") or "",
    }


def get_llm_client(api_key: str = None, api_base: str = None) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or settings.llm_api_key,
        base_url=api_base or settings.llm_api_base
    )


async def test_connection(db: Optional[AsyncSession] = None) -> str:
    config = await get_llm_config(db)
    logger.info(f"[LLM TEST] API Key length: {len(config['api_key'])}")
    logger.info(f"[LLM TEST] API Key: {config['api_key'][:10]}...")
    logger.info(f"[LLM TEST] API Base: {config['api_base']}")
    logger.info(f"[LLM TEST] Model: {config['model']}")
    client = get_llm_client(config["api_key"], config["api_base"])

    response = await client.chat.completions.create(
        model=config["model"],
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=10
    )

    return config["model"]


async def generate_tweet_content(
    topic: str,
    style: str = "professional",
    language: str = "en",
    max_length: int = 280,
    template_prompt: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> Tuple[str, Optional[int]]:
    config = await get_llm_config(db)
    client = get_llm_client(config["api_key"], config["api_base"])

    if template_prompt:
        prompt = template_prompt.format(topic=topic)
    else:
        prompt = f"""Generate a tweet about: {topic}

Style: {style}
Language: {language}
Maximum length: {max_length} characters

Requirements:
- Be engaging and interesting
- Use appropriate hashtags
- Keep within Twitter's character limit
- Match the requested style and language

Output only the tweet content, nothing else."""

    response = await client.chat.completions.create(
        model=config["model"],
        messages=[
            {
                "role": "system",
                "content": "You are a professional social media content creator specializing in Web3 and crypto projects. Create engaging, authentic tweets that drive engagement."
            },
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        **({} if "reasoner" in config["model"] else {"temperature": 0.8})
    )

    content = response.choices[0].message.content or ""
    content = content.strip().strip('"').strip("'")

    # 确保不超过长度限制
    if len(content) > max_length:
        content = content[:max_length-3] + "..."

    tokens_used = response.usage.total_tokens if response.usage else None

    return content, tokens_used
