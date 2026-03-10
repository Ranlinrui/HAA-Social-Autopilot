from pydantic import BaseModel
from typing import Optional, Dict, Any


class SettingUpdate(BaseModel):
    value: str


class SettingResponse(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


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
