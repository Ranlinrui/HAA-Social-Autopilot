from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
import json
import os

from app.database import get_db
from app.models.setting import Setting
from app.schemas.setting import (
    SettingUpdate, SettingResponse, SettingsResponse,
    TwitterTestResponse, LLMTestResponse,
    TwitterLoginRequest, TwitterLoginResponse
)
from app.config import settings as app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


COOKIE_FILE = "/app/data/twitter_cookies.json"


def _load_cookie_mode_state() -> Dict[str, Any] | None:
    try:
        if not os.path.exists(COOKIE_FILE):
            return None
        with open(COOKIE_FILE, 'r') as f:
            data = json.load(f)
        if not data.get('auth_token') or not data.get('ct0'):
            return None
        return data
    except Exception:
        return None


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    db_settings = result.scalars().all()

    settings_dict: Dict[str, Any] = {
        "llm_model": app_settings.llm_model,
        "llm_api_base": app_settings.llm_api_base,
        "twitter_publish_mode": app_settings.twitter_publish_mode,
    }

    for s in db_settings:
        settings_dict[s.key] = s.value

    # 如果数据库中有保存的 twitter 凭证，返回用户名和邮箱（密码用掩码）
    if "twitter_username" in settings_dict:
        pass  # 已在循环中设置
    if "twitter_password" in settings_dict and settings_dict["twitter_password"]:
        settings_dict["twitter_password_saved"] = True
        del settings_dict["twitter_password"]

    # 如果数据库中有保存的 llm_api_key，用掩码显示
    if "llm_api_key" in settings_dict and settings_dict["llm_api_key"]:
        settings_dict["llm_api_key_saved"] = True
        # 显示前4位和后4位，中间用星号
        key = settings_dict["llm_api_key"]
        if len(key) > 8:
            settings_dict["llm_api_key"] = f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
        else:
            settings_dict["llm_api_key"] = "****"

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

    cookie_state = _load_cookie_mode_state()
    if cookie_state:
        credentials = [
            ("twitter_username", data.username),
            ("twitter_email", data.email),
        ]
        if data.password:
            credentials.append(("twitter_password", data.password))

        for key, value in credentials:
            result = await db.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                db.add(Setting(key=key, value=value))

        await db.commit()
        reset_twitter_twikit()
        fallback_username = cookie_state.get("account_name") or data.username
        return TwitterLoginResponse(
            success=True,
            message="Cookie 模式已启用：检测到本地 auth_token/ct0，跳过 live twikit 登录验证",
            username=fallback_username,
        )

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
        cookie_state = _load_cookie_mode_state()
        if cookie_state:
            for key, value in [("twitter_username", data.username), ("twitter_email", data.email)]:
                result = await db.execute(select(Setting).where(Setting.key == key))
                setting = result.scalar_one_or_none()
                if setting:
                    setting.value = value
                else:
                    db.add(Setting(key=key, value=value))
            if data.password:
                result = await db.execute(select(Setting).where(Setting.key == "twitter_password"))
                setting = result.scalar_one_or_none()
                if setting:
                    setting.value = data.password
                else:
                    db.add(Setting(key="twitter_password", value=data.password))
            await db.commit()
            reset_twitter_twikit()
            fallback_username = cookie_state.get("account_name") or data.username
            return TwitterLoginResponse(
                success=True,
                message="Cookie 模式已启用：已保存账号配置并检测到本地 auth_token/ct0，跳过 live twikit 登录验证",
                username=fallback_username
            )

        return TwitterLoginResponse(
            success=False,
            message=f"登录失败: {str(e)}"
        )


@router.post("/test-twitter", response_model=TwitterTestResponse)
async def test_twitter_connection():
    from app.services.twitter_api import test_connection

    cookie_state = _load_cookie_mode_state()
    if cookie_state:
        username = cookie_state.get("account_name") or cookie_state.get("username") or "default"
        return TwitterTestResponse(
            success=True,
            message="Twitter cookie 已加载，当前使用 Cookie 模式，跳过 live twikit transaction 验证",
            username=username
        )

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
async def test_llm_connection(db: AsyncSession = Depends(get_db)):
    from app.services.llm_service import test_connection
    import logging
    logger = logging.getLogger(__name__)

    try:
        model = await test_connection(db)
        return LLMTestResponse(
            success=True,
            message="LLM connection successful",
            model=model
        )
    except Exception as e:
        logger.error(f"[LLM TEST ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[LLM TEST TRACEBACK] {traceback.format_exc()}")
        return LLMTestResponse(
            success=False,
            message=str(e)
        )
