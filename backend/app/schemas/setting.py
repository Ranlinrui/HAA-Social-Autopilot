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


class TwitterBrowserSessionResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None
    ready: bool = False
    updated_at: Optional[datetime] = None


class TwitterBrowserTakeoverRequest(BaseModel):
    username: str
    email: Optional[str] = None
    password: Optional[str] = None


class TwitterBrowserTakeoverResponse(BaseModel):
    success: bool
    message: str
    username: Optional[str] = None
    account_key: Optional[str] = None
    ready: bool = False
    manual_login_active: bool = False
    vnc_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    session_health: Optional[Dict[str, Any]] = None


class TwitterAccountUpsertRequest(BaseModel):
    account_key: str
    username: str
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: bool = False


class TwitterAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_key: str
    username: str
    email: Optional[str] = None
    is_active: bool
    password_saved: bool = False
    cookie_ready: bool = False
    browser_session_ready: bool = False
    automation_ready: bool = False
    last_login_status: Optional[str] = None
    last_login_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TwitterAccountHealthCheckResponse(BaseModel):
    success: bool
    account_key: str
    username: str
    cookie_ready: bool = False
    browser_session_ready: bool = False
    automation_ready: bool = False
    twikit_ok: bool = False
    twikit_message: str
    browser_message: str
    checked_at: datetime


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
