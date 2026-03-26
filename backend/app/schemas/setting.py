from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class SettingUpdate(BaseModel):
    value: str


class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Optional[str] = None
    description: Optional[str] = None


class SettingsResponse(BaseModel):
    settings: Dict[str, Any]


class TwitterTestResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None


class LLMTestResponse(BaseModel):
    success: bool
    message: str
    model: Optional[str] = None


class TwitterLoginRequest(BaseModel):
    username: str
    email: str
    password: Optional[str] = None


class TwitterLoginResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None


class TwitterAuthStateResponse(BaseModel):
    feature: str
    selected_mode: str
    default_mode: str
    cookie_configured: bool
    cookie_validation_mode: Optional[str] = None
    cookie_username: Optional[str] = None
    configured_username: Optional[str] = None
    active_username: Optional[str] = None
    risk_stage: Optional[str] = None
    write_blocked: bool = False
    write_block_reason: Optional[str] = None
    write_resume_seconds: int = 0
    auth_backoff_until: Optional[datetime] = None
    read_only_until: Optional[datetime] = None
    recovery_until: Optional[datetime] = None
    last_risk_error: Optional[str] = None
    last_risk_event_at: Optional[datetime] = None


class TwitterRiskAccountResponse(BaseModel):
    risk_account_key: str
    risk_stage: str
    is_persisted: bool = False
    is_active_display_only: bool = False
    write_blocked: bool = False
    write_block_reason: Optional[str] = None
    write_resume_seconds: int = 0
    auth_backoff_until: Optional[datetime] = None
    read_only_until: Optional[datetime] = None
    recovery_until: Optional[datetime] = None
    last_risk_error: Optional[str] = None
    last_risk_event_at: Optional[datetime] = None
