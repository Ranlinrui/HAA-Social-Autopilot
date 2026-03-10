from openai import AsyncOpenAI
from typing import Optional, Tuple
from app.config import settings


def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base
    )


async def test_connection() -> str:
    client = get_llm_client()

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=10
    )

    return settings.llm_model


async def generate_tweet_content(
    topic: str,
    style: str = "professional",
    language: str = "en",
    max_length: int = 280,
    template_prompt: Optional[str] = None
) -> Tuple[str, Optional[int]]:
    client = get_llm_client()

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
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": "You are a professional social media content creator specializing in Web3 and crypto projects. Create engaging, authentic tweets that drive engagement."
            },
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        **({} if "reasoner" in settings.llm_model else {"temperature": 0.8})
    )

    content = response.choices[0].message.content or ""
    content = content.strip().strip('"').strip("'")

    # 确保不超过长度限制
    if len(content) > max_length:
        content = content[:max_length-3] + "..."

    tokens_used = response.usage.total_tokens if response.usage else None

    return content, tokens_used
