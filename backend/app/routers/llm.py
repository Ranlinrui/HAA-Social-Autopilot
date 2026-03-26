from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.services.llm_service import generate_tweet_content

router = APIRouter(prefix="/api/llm", tags=["llm"])


def _error_detail(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


class GenerateRequest(BaseModel):
    topic: str
    style: Optional[str] = "professional"
    language: Optional[str] = "en"
    max_length: Optional[int] = 280
    template_id: Optional[str] = None


class GenerateResponse(BaseModel):
    content: str
    tokens_used: Optional[int] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    prompt: str


TEMPLATES = [
    TemplateResponse(
        id="ai_reasoning",
        name="AI 推理展示",
        description="展示 AI 的交易决策推理过程，适合配合 HAA 截图发布",
        prompt="""You are a quant trader with 3 years of experience, sharing your trading tools and thoughts on Twitter.

AI decision reasoning from the platform:
{topic}

Write a tweet. Requirements:

Persona: quant practitioner who has seen many systems and has genuine feelings about this one. Not selling, just sharing something interesting.

Structure:
- First line: a question or observation that makes people want to keep reading
- Middle: quote or paraphrase the AI reasoning (can be condensed)
- Last line: your own take — could be approval or skepticism

Style:
- Mix Chinese/English naturally based on content
- Short sentences, good rhythm
- No exclamation marks, no words like "shocking" or "revolutionary"
- At most 1 relevant hashtag

Product mention (Hyper Alpha Arena):
- Only mention if the reasoning content is genuinely interesting
- Casual mention only: "this is from a DeepSeek decision log in Hyper Alpha Arena"
- Never pitch features

Hard rules:
- Under 280 characters (Chinese tweets under 140 chars)
- Complete sentences
- Output only the tweet, nothing else."""
    ),
    TemplateResponse(
        id="trade_report",
        name="交易战报",
        description="晒 AI 交易账户的真实数据，普通玩家视角",
        prompt="""You are an ordinary person experimenting with AI trading tools, documenting your experience on Twitter.

Trade data:
{topic}

Write a tweet. Requirements:

Persona: regular player, not an institution, just tinkering. A bit curious, a bit zen.

Structure:
- Lead with the numbers directly, no preamble
- Add one personal observation or feeling after the data
- Optional: open-ended ending (question to readers, or a cliffhanger)

Style:
- Casual, like a WeChat Moments post
- Numbers must be specific, don't vague them out
- Don't hide losses — authenticity beats looking good
- 1-2 hashtags ok

Product mention (Hyper Alpha Arena):
- The report itself is indirect product exposure, no need to add more
- Only add "running on Hyper Alpha Arena" if the numbers are particularly good

Hard rules:
- Under 280 characters
- Output only the tweet, nothing else."""
    ),
    TemplateResponse(
        id="ai_vs_ai",
        name="AI 对比实验",
        description="对比不同 AI 模型的交易表现，引发讨论",
        prompt="""You are a quant practitioner running a controlled experiment comparing AI trading models, sharing results on Twitter.

Comparison data:
{topic}

Write a tweet. Requirements:

Persona: running a serious comparison experiment, but speaking plainly, not academically. Has your own judgment, not just listing data.

Structure:
- Lead with the conclusion or the most counterintuitive finding
- Support with data
- Last line: your interpretation or a question for readers

Style:
- Use contrast phrasing ("same market, A did X, B did Y")
- No tables, use natural language
- Calm tone, no hype

Product mention (Hyper Alpha Arena):
- The comparison itself demonstrates platform capability
- Can add "both running on Hyper Alpha Arena" at the end, but not required

Hard rules:
- Under 280 characters
- Output only the tweet, nothing else."""
    ),
    TemplateResponse(
        id="hot_take",
        name="蹭热点",
        description="市场大事件发生时，从 AI 交易角度切入",
        prompt="""You are a crypto trader with a quant background, commenting on market events from an AI trading perspective on Twitter.

Current event:
{topic}

Write a tweet. Requirements:

Persona — pick one randomly:
a) Quant practitioner: calm analysis, "how would an AI system react to this market"
b) Regular player: emotional, "my AI actually did X at this price level"

Structure:
- Hook onto the event (1 sentence)
- Your angle or the AI's reaction (1-2 sentences)
- Optional: a question or opinion to spark engagement

Style:
- Ride the trend but have your own angle, don't just follow the crowd
- No price predictions, no calls to buy/sell
- Can be wry, but not mocking

Product mention (Hyper Alpha Arena):
- Only mention if there's specific AI behavior data to share
- Keep it natural, not jarring

Hard rules:
- Under 280 characters
- Output only the tweet, nothing else."""
    ),
    TemplateResponse(
        id="story",
        name="故事叙事",
        description="记录 AI 交易中的具体经历，真实感最强",
        prompt="""You are an ordinary person using AI for trading, documenting this experience on Twitter.

Story material:
{topic}

Write a tweet. Requirements:

Persona: regular person, not an expert, genuinely documenting. A bit self-deprecating, a bit curious, occasionally reflective.

Structure:
- Open with a specific detail or moment
- Expand on what's interesting about that detail
- End with a reflection, question, or what happens next

Style:
- Talk like you're telling a friend
- Details must be specific (time, price, what the AI said)
- Don't moralize, don't summarize "what this means"

Product mention (Hyper Alpha Arena):
- Let it appear naturally in the story, no need to highlight it
- Good: "last night DeepSeek in Hyper Alpha Arena chose to add to its position when BTC broke below 90k"
- Bad: "Hyper Alpha Arena is a great tool"

Hard rules:
- Under 280 characters
- Output only the tweet, nothing else."""
    ),
]


@router.get("/templates", response_model=List[TemplateResponse])
async def get_templates():
    return TEMPLATES


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest):
    template_prompt = None

    if request.template_id:
        template = next((t for t in TEMPLATES if t.id == request.template_id), None)
        if template:
            template_prompt = template.prompt

    try:
        content, tokens = await generate_tweet_content(
            topic=request.topic,
            style=request.style or "professional",
            language=request.language or "en",
            max_length=request.max_length or 280,
            template_prompt=template_prompt
        )

        return GenerateResponse(content=content, tokens_used=tokens)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))
