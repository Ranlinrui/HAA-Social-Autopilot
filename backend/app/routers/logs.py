from fastapi import APIRouter, Query
from typing import Optional
from app.logger import get_logs

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def list_logs(
    level: Optional[str] = Query(None, description="ERROR / WARNING / INFO / DEBUG"),
    module: Optional[str] = Query(None, description="twikit / scheduler / tweets / engage"),
    limit: int = Query(100, ge=1, le=500),
):
    return get_logs(level=level, module=module, limit=limit)
