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
    TwitterLoginRequest, TwitterLoginResponse, TwitterAuthStateResponse, TwitterRiskAccountResponse
)
from app.config import settings as app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


COOKIE_FILE = "/app/data/twitter_cookies.json"

TWITTER_MODE_DEFAULTS: Dict[str, Any] = {
    "twitter_publish_mode": app_settings.twitter_publish_mode,
    "twitter_mode_test_connection": "twikit",
    "twitter_mode_publish": "twikit",
    "twitter_mode_search": "twikit",
    "twitter_mode_reply": "twikit",
    "twitter_mode_retweet": "twikit",
    "twitter_mode_quote": "twikit",
    "twitter_mode_mentions": "twikit",
    "twitter_mode_tweet_lookup": "twikit",
}


def _normalize_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"browser", "playwright"}:
        return "browser"
    return "twikit"


def _get_selected_mode(settings_dict: Dict[str, Any], key: str) -> str:
    return _normalize_mode(str(settings_dict.get(key, TWITTER_MODE_DEFAULTS.get(key, "twikit"))))


def _get_feature_mode(settings_dict: Dict[str, Any], feature_key: str) -> str:
    feature_value = settings_dict.get(feature_key)
    if feature_value:
        return _normalize_mode(str(feature_value))
    return _get_selected_mode(settings_dict, "twitter_publish_mode")


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


def _error_detail(exc: Exception, fallback: str) -> str:
    detail = str(exc).strip()
    return detail or fallback


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Setting))
        db_settings = result.scalars().all()

        settings_dict: Dict[str, Any] = {
            "llm_model": app_settings.llm_model,
            "llm_api_base": app_settings.llm_api_base,
            **TWITTER_MODE_DEFAULTS,
        }

        for s in db_settings:
            settings_dict[s.key] = s.value

        _get_selected_mode(settings_dict, "twitter_publish_mode")

        if "twitter_username" in settings_dict:
            pass
        if "twitter_password" in settings_dict and settings_dict["twitter_password"]:
            settings_dict["twitter_password_saved"] = True
            del settings_dict["twitter_password"]

        if "llm_api_key" in settings_dict and settings_dict["llm_api_key"]:
            settings_dict["llm_api_key_saved"] = True
            key = settings_dict["llm_api_key"]
            if len(key) > 8:
                settings_dict["llm_api_key"] = f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
            else:
                settings_dict["llm_api_key"] = "****"

        return SettingsResponse(settings=settings_dict)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载设置失败"))


@router.get("/twitter-auth-state", response_model=TwitterAuthStateResponse)
async def get_twitter_auth_state():
    from app.services.twitter_api import get_active_auth_state
    try:
        return TwitterAuthStateResponse(**(await get_active_auth_state()))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载 Twitter 认证状态失败"))


@router.get("/twitter-risk-accounts", response_model=list[TwitterRiskAccountResponse])
async def get_twitter_risk_accounts():
    from app.services.twitter_api import get_active_auth_state
    from app.services.twitter_risk_control import get_twitter_risk_control
    try:
        risk_control = get_twitter_risk_control()
        rows = risk_control.list_states()
        active_username = (await get_active_auth_state()).get("active_username")
        if active_username and not any(item["risk_account_key"] == active_username for item in rows):
            row = risk_control.get_state(active_username)
            row["is_active_display_only"] = True
            rows.append(row)
        for item in rows:
            item.setdefault("is_active_display_only", False)
        rows.sort(key=lambda item: (item["risk_account_key"] != active_username, item["risk_account_key"]))
        return [TwitterRiskAccountResponse(**item) for item in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载 Twitter 风控账号失败"))


@router.delete("/twitter-risk-accounts/{account_key}")
async def reset_twitter_risk_account(account_key: str):
    from app.services.twitter_risk_control import get_twitter_risk_control
    try:
        removed = get_twitter_risk_control().reset_account(account_key)
        return {
            "success": True,
            "message": f"已重置账号 @{account_key} 的风控内存状态" if removed else f"账号 @{account_key} 当前没有可清理的真实风控记录",
            "removed": removed,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "重置 Twitter 风控状态失败"))


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    data: SettingUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "保存设置失败"))


@router.post("/twitter-login", response_model=TwitterLoginResponse)
async def twitter_login(
    data: TwitterLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    from app.services.twitter_browser import login_browser
    from app.services.twitter_twikit import TwitterTwikit, reset_twitter_twikit

    result = await db.execute(select(Setting))
    db_settings = {item.key: item.value for item in result.scalars().all()}
    selected_mode = _get_selected_mode(db_settings, "twitter_publish_mode")

    if selected_mode == "browser":
        password = data.password
        if not password:
            result = await db.execute(select(Setting).where(Setting.key == "twitter_password"))
            saved = result.scalar_one_or_none()
            password = saved.value if saved else None
        if not password:
            return TwitterLoginResponse(success=False, message="登录失败: Browser 模式缺少密码")

        try:
            browser_username = await login_browser(data.username, data.email, password)
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            return TwitterLoginResponse(success=False, message=f"登录失败: {message}")

        credentials = [
            ("twitter_username", data.username),
            ("twitter_email", data.email),
            ("twitter_password", password),
        ]
        for key, value in credentials:
            result = await db.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                db.add(Setting(key=key, value=value))

        await db.commit()
        reset_twitter_twikit()
        return TwitterLoginResponse(
            success=True,
            message="Browser 模式登录成功",
            username=browser_username,
        )

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
async def test_twitter_connection(db: AsyncSession = Depends(get_db)):
    from app.services.twitter_api import get_active_auth_state, test_connection

    auth_state = await get_active_auth_state("test_connection")
    if auth_state["cookie_configured"]:
        username = auth_state.get("active_username") or "default"
        return TwitterTestResponse(
            success=True,
            message="Twitter Cookie 已加载，当前优先使用 Cookie 模式，跳过 Browser/Twikit 的实时登录校验",
            username=username
        )

    result = await db.execute(select(Setting))
    db_settings = {item.key: item.value for item in result.scalars().all()}
    selected_mode = _get_feature_mode(db_settings, "twitter_mode_test_connection")

    if selected_mode == "browser":
        try:
            username = await test_connection()
            return TwitterTestResponse(
                success=True,
                message="Browser 模式连接成功",
                username=username,
            )
        except Exception as e:
            return TwitterTestResponse(
                success=False,
                message=str(e),
            )

    try:
        username = await test_connection()
        return TwitterTestResponse(
            success=True,
            message="Twitter 连接成功",
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
