from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.media import MediaType


class MediaResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    filepath: str
    media_type: MediaType
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    tags: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MediaListResponse(BaseModel):
    total: int
    items: List[MediaResponse]
