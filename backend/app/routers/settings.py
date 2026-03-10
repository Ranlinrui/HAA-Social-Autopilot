from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from app.database import get_db
from app.models.setting import Setting
from app.schemas.setting import (
    SettingUpdate, SettingResponse, SettingsResponse,
    TwitterTestResponse, LLMTestResponse,
    TwitterLoginRequest, TwitterLoginResponse
)
from app.config import settings as app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    db_settings = result.scalars().all()

    settings_dict: Dict[str, Any] = {
        "llm_model": app_settings.llm_model,
        "llm_api_base": app_settings.llm_api_base,
    }

    for s in db_settings:
        settings_dict[s.key] = s.value

    # 如果数据库中有保存的 twitter 凭证，返回用户名和邮箱（密码用掩码）
    if "twitter_username" in settings_dict:
        pass  # 已在循环中设置
    if "twitter_password" in settings_dict and settings_dict["twitter_password"]:
        settings_dict["twitter_password_saved"] = True
        del settings_dict["twitter_password"]

    return SettingsResponse(settings=settings_dict)


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    data: SettingUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Setting).where(Setting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = data.value
    else:
        setting = Setting(key=key, value=data.value)
        db.add(setting)

    await db.commit()
    await db.refresh(setting)

    return setting


@router.post("/twitter-login", response_model=TwitterLoginResponse)
async def twitter_login(
    data: TwitterLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    from app.services.twitter_twikit import TwitterTwikit, reset_twitter_twikit

    try:
        # 如果未传密码，从数据库读取已保存的密码
        password = data.password
        if not password:
            result = await db.execute(
                select(Setting).where(Setting.key == "twitter_password")
            )
            saved = result.scalar_one_or_none()
            if saved:
                password = saved.value
            else:
                return TwitterLoginResponse(
                    success=False,
                    message="登录失败: 未提供密码且无已保存密码"
                )

        # 用传入的凭证尝试登录
        twikit = TwitterTwikit()
        await twikit.login(
            username=data.username,
            email=data.email,
            password=password
        )
        me = await twikit.get_me()

        # 登录成功，保存凭证到数据库
        credentials = [
            ("twitter_username", data.username),
            ("twitter_email", data.email),
        ]
        if data.password:
            credentials.append(("twitter_password", data.password))

        for key, value in credentials:
            result = await db.execute(
                select(Setting).where(Setting.key == key)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                db.add(Setting(key=key, value=value))

        await db.commit()

        # 重置全局单例，下次使用时会用新的 cookie
        reset_twitter_twikit()

        return TwitterLoginResponse(
            success=True,
            message="登录成功",
            username=me["username"]
        )
    except Exception as e:
        return TwitterLoginResponse(
            success=False,
            message=f"登录失败: {str(e)}"
        )


@router.post("/test-twitter", response_model=TwitterTestResponse)
async def test_twitter_connection():
    from app.services.twitter_api import test_connection

    try:
        username = await test_connection()
        return TwitterTestResponse(
            success=True,
            message="Twitter connection successful",
            username=username
        )
    except Exception as e:
        return TwitterTestResponse(
            success=False,
            message=str(e)
        )


@router.post("/test-llm", response_model=LLMTestResponse)
async def test_llm_connection():
    from app.services.llm_service import test_connection

    try:
        model = await test_connection()
        return LLMTestResponse(
            success=True,
            message="LLM connection successful",
            model=model
        )
    except Exception as e:
        return LLMTestResponse(
            success=False,
            message=str(e)
        )
