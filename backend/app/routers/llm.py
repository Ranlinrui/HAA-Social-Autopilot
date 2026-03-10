from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.services.llm_service import generate_tweet_content

router = APIRouter(prefix="/api/llm", tags=["llm"])


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
        id="announcement",
        name="项目公告",
        description="用于发布项目重大更新和公告",
        prompt="Generate a professional announcement tweet about: {topic}. Keep it exciting but informative."
    ),
    TemplateResponse(
        id="engagement",
        name="社区互动",
        description="用于提升社区互动和讨论",
        prompt="Generate an engaging tweet that encourages community discussion about: {topic}. Ask a thought-provoking question."
    ),
    TemplateResponse(
        id="educational",
        name="知识分享",
        description="用于分享行业知识和见解",
        prompt="Generate an educational tweet explaining: {topic}. Make it easy to understand but insightful."
    ),
    TemplateResponse(
        id="hype",
        name="造势宣传",
        description="用于制造话题热度和期待感",
        prompt="Generate an exciting hype tweet about: {topic}. Create anticipation and excitement!"
    ),
    TemplateResponse(
        id="milestone",
        name="里程碑",
        description="用于庆祝项目成就和里程碑",
        prompt="Generate a celebratory tweet about this milestone: {topic}. Express gratitude to the community."
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
        raise HTTPException(status_code=500, detail=str(e))
