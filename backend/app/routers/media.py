from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import os
import uuid
import aiofiles
from PIL import Image
from datetime import datetime

from app.database import get_db
from app.config import settings
from app.models.media import Media, MediaType
from app.schemas.media import MediaResponse, MediaListResponse

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}


@router.get("", response_model=MediaListResponse)
async def get_media_list(
    media_type: Optional[MediaType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Media)

    if media_type:
        query = query.where(Media.media_type == media_type)

    query = query.order_by(Media.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    media_items = result.scalars().all()

    count_query = select(func.count(Media.id))
    if media_type:
        count_query = count_query.where(Media.media_type == media_type)
    total = await db.execute(count_query)
    total = total.scalar()

    return MediaListResponse(total=total, items=media_items)


@router.post("/upload", response_model=MediaResponse)
async def upload_media(
    file: UploadFile = File(...),
    tags: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # 确定媒体类型
    if file.content_type in ALLOWED_IMAGE_TYPES:
        media_type = MediaType.IMAGE
    elif file.content_type in ALLOWED_VIDEO_TYPES:
        media_type = MediaType.VIDEO
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}"
        )

    # 读取文件内容
    content = await file.read()
    file_size = len(content)

    if file_size > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_upload_size / 1024 / 1024}MB"
        )

    # 生成唯一文件名
    ext = os.path.splitext(file.filename or "file")[1]
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    # 按日期组织目录
    date_dir = datetime.now().strftime("%Y/%m")
    upload_dir = os.path.join(settings.upload_dir, date_dir)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, unique_filename)

    # 保存文件
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    # 获取图片尺寸
    width, height = None, None
    if media_type == MediaType.IMAGE:
        try:
            with Image.open(filepath) as img:
                width, height = img.size
        except Exception:
            pass

    # 创建数据库记录
    media = Media(
        filename=unique_filename,
        original_filename=file.filename or "unknown",
        filepath=filepath,
        media_type=media_type,
        mime_type=file.content_type,
        file_size=file_size,
        width=width,
        height=height,
        tags=tags
    )

    db.add(media)
    await db.commit()
    await db.refresh(media)

    return media


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Media).where(Media.id == media_id)
    )
    media = result.scalar_one_or_none()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # 删除文件
    if os.path.exists(media.filepath):
        os.remove(media.filepath)

    await db.delete(media)
    await db.commit()

    return {"message": "Media deleted"}
