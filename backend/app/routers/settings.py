from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Dict, Any
from datetime import datetime, timezone
import json
import os

from app.database import get_db
from app.models.setting import Setting
from app.models.twitter_account import TwitterAccount
from app.schemas.setting import (
    SettingUpdate, SettingResponse, SettingsResponse,
    TwitterTestResponse, LLMTestResponse,
    TwitterLoginRequest, TwitterLoginResponse, TwitterAuthStateResponse, TwitterRiskAccountResponse,
    TwitterAccountUpsertRequest, TwitterAccountResponse, TwitterBrowserSessionResponse,
    TwitterBrowserTakeoverRequest, TwitterBrowserTakeoverResponse, TwitterAccountHealthCheckResponse,
)
from app.config import settings as app_settings
from app.services.twitter_account_store import (
    get_account_browser_storage_file,
    get_account_cookie_file,
    load_cookie_file,
    sync_account_cookie_to_global,
    sync_global_cookie_to_account,
    using_twitter_account,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


COOKIE_FILE = "/app/data/twitter_cookies.json"
LOGIN_DIAGNOSTIC_FILE = "/app/data/twitter_browser_login_diagnostic.json"
ACTIVE_TWITTER_ACCOUNT_KEY = "active_twitter_account_id"

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

MODE_PRESETS: Dict[str, Dict[str, str]] = {
    "low_cost": {
        "twitter_publish_mode": "twikit",
        "twitter_mode_test_connection": "twikit",
        "twitter_mode_publish": "twikit",
        "twitter_mode_search": "twikit",
        "twitter_mode_reply": "twikit",
        "twitter_mode_retweet": "twikit",
        "twitter_mode_quote": "twikit",
        "twitter_mode_mentions": "twikit",
        "twitter_mode_tweet_lookup": "twikit",
    },
    "high_availability": {
        "twitter_publish_mode": "twikit",
        "twitter_mode_test_connection": "browser",
        "twitter_mode_publish": "twikit",
        "twitter_mode_search": "browser",
        "twitter_mode_reply": "twikit",
        "twitter_mode_retweet": "twikit",
        "twitter_mode_quote": "twikit",
        "twitter_mode_mentions": "browser",
        "twitter_mode_tweet_lookup": "browser",
    },
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


@router.get("/twitter-mode-presets")
async def get_twitter_mode_presets():
    return {
        "success": True,
        "presets": [
            {
                "key": "low_cost",
                "label": "低成本模式",
                "description": "绝大多数能力走 Twikit，Browser 仅保留登录接管和会话同步，适合长期低流量运行。",
                "settings": MODE_PRESETS["low_cost"],
            },
            {
                "key": "high_availability",
                "label": "高可用模式",
                "description": "搜索、提及和推文读取优先走 Browser，写入仍保留 Twikit，适合需要更强读取稳定性的场景。",
                "settings": MODE_PRESETS["high_availability"],
            },
        ],
    }


@router.post("/twitter-mode-presets/{preset_key}")
async def apply_twitter_mode_preset(
    preset_key: str,
    db: AsyncSession = Depends(get_db),
):
    preset = MODE_PRESETS.get((preset_key or "").strip())
    if preset is None:
        raise HTTPException(status_code=404, detail="未找到目标模式预设")

    try:
        for key, value in preset.items():
            await _upsert_setting(db, key, value)
        await db.commit()
        return {
            "success": True,
            "message": f"已切换到{ '低成本模式' if preset_key == 'low_cost' else '高可用模式' }",
            "preset_key": preset_key,
            "settings": preset,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "切换 Twitter 模式预设失败"))


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


def _load_browser_login_diagnostic() -> Dict[str, Any] | None:
    try:
        if not os.path.exists(LOGIN_DIAGNOSTIC_FILE):
            return None
        with open(LOGIN_DIAGNOSTIC_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


async def _upsert_setting(db: AsyncSession, key: str, value: str | None):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
        return setting
    setting = Setting(key=key, value=value)
    db.add(setting)
    return setting


def _serialize_twitter_account(account: TwitterAccount) -> TwitterAccountResponse:
    cookie_ready = load_cookie_file(get_account_cookie_file(account.account_key)) is not None
    browser_session_ready = os.path.exists(get_account_browser_storage_file(account.account_key))
    return TwitterAccountResponse(
        id=account.id,
        account_key=account.account_key,
        username=account.username,
        email=account.email,
        is_active=bool(account.is_active),
        password_saved=bool(account.password),
        cookie_ready=cookie_ready,
        browser_session_ready=browser_session_ready,
        automation_ready=bool(cookie_ready or browser_session_ready),
        last_login_status=account.last_login_status,
        last_login_message=account.last_login_message,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


async def _check_twitter_account_health(account: TwitterAccount) -> TwitterAccountHealthCheckResponse:
    from app.services.twitter_browser import get_twitter_browser
    from app.services.twitter_twikit import TwitterTwikit

    cookie_ready = load_cookie_file(get_account_cookie_file(account.account_key)) is not None
    browser = await get_twitter_browser()
    browser_session = browser.get_session_status(account.account_key)
    browser_session_ready = bool(browser_session.get("ready"))

    twikit_ok = False
    if cookie_ready:
        try:
            async with using_twitter_account(account.account_key):
                twitter = TwitterTwikit()
                await twitter.init_client()
                me = await twitter.get_me()
            twikit_ok = True
            twikit_message = f"Twikit 认证有效，当前身份 @{me.get('username') or account.username}"
        except Exception as exc:
            twikit_message = f"Twikit 校验失败：{_error_detail(exc, '未知错误')}"
    else:
        twikit_message = "未检测到该账号的有效 Cookie，跳过 Twikit 实时校验"

    browser_message = (
        "检测到该账号的独立 Browser 会话文件"
        if browser_session_ready
        else "未检测到该账号的独立 Browser 会话文件"
    )

    return TwitterAccountHealthCheckResponse(
        success=True,
        account_key=account.account_key,
        username=account.username,
        cookie_ready=cookie_ready,
        browser_session_ready=browser_session_ready,
        automation_ready=bool(twikit_ok or browser_session_ready),
        twikit_ok=twikit_ok,
        twikit_message=twikit_message,
        browser_message=browser_message,
        checked_at=datetime.now(timezone.utc),
    )


def _build_browser_takeover_url(request: Request) -> str:
    host = request.url.hostname or "127.0.0.1"
    return f"http://{host}:{app_settings.backend_vnc_port}/vnc.html?autoconnect=1&resize=scale&view_only=0"


async def _sync_active_account_settings(db: AsyncSession, account: TwitterAccount | None):
    await _upsert_setting(db, ACTIVE_TWITTER_ACCOUNT_KEY, str(account.id) if account else "")
    await _upsert_setting(db, "twitter_username", account.username if account else "")
    await _upsert_setting(db, "twitter_email", account.email if account else "")
    await _upsert_setting(db, "twitter_password", account.password if account else "")


async def _set_active_twitter_account(db: AsyncSession, account: TwitterAccount | None):
    await db.execute(update(TwitterAccount).values(is_active=False))
    if account is not None:
        account.is_active = True
    await _sync_active_account_settings(db, account)


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


@router.get("/twitter-login-diagnostic")
async def get_twitter_login_diagnostic():
    return {
        "success": True,
        "diagnostic": _load_browser_login_diagnostic(),
    }


@router.get("/twitter-browser-session", response_model=TwitterBrowserSessionResponse)
async def get_twitter_browser_session():
    from app.services.twitter_browser import get_browser_session_status

    try:
        status = await get_browser_session_status()
        return TwitterBrowserSessionResponse(
            success=True,
            message="Browser 会话已就绪" if status.get("ready") else "Browser 会话尚未初始化",
            ready=bool(status.get("ready")),
            updated_at=status.get("updated_at"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载 Browser 会话状态失败"))


@router.post("/twitter-browser-session/sync", response_model=TwitterBrowserSessionResponse)
async def sync_twitter_browser_session():
    from app.services.twitter_browser import get_browser_session_status, sync_browser_session

    try:
        username = await sync_browser_session()
        status = await get_browser_session_status()
        return TwitterBrowserSessionResponse(
            success=True,
            message="当前认证已同步到 Browser 会话，后续将优先复用该账号会话",
            username=username,
            ready=bool(status.get("ready")),
            updated_at=status.get("updated_at"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "同步 Browser 会话失败"))


@router.get("/twitter-browser-takeover", response_model=TwitterBrowserTakeoverResponse)
async def get_twitter_browser_takeover_status(request: Request):
    from app.services.twitter_browser import get_manual_browser_login_status

    try:
        status = await get_manual_browser_login_status()
        return TwitterBrowserTakeoverResponse(
            success=True,
            message="人工接管浏览器已就绪" if status.get("manual_login_active") else "当前没有进行中的人工接管登录",
            username=status.get("username"),
            account_key=status.get("account_key"),
            ready=bool(status.get("ready")),
            manual_login_active=bool(status.get("manual_login_active")),
            vnc_url=_build_browser_takeover_url(request),
            updated_at=status.get("updated_at"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载人工接管浏览器状态失败"))


@router.post("/twitter-browser-takeover/start", response_model=TwitterBrowserTakeoverResponse)
async def start_twitter_browser_takeover(
    data: TwitterBrowserTakeoverRequest,
    request: Request,
):
    from app.services.twitter_browser import start_manual_browser_login

    try:
        status = await start_manual_browser_login(data.username, data.email)
        return TwitterBrowserTakeoverResponse(
            success=True,
            message="人工接管浏览器已启动，请在新窗口中亲自完成登录",
            username=status.get("username"),
            account_key=status.get("account_key"),
            ready=bool(status.get("ready")),
            manual_login_active=bool(status.get("manual_login_active")),
            vnc_url=_build_browser_takeover_url(request),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "启动人工接管浏览器失败"))


@router.post("/twitter-browser-takeover/complete", response_model=TwitterBrowserTakeoverResponse)
async def complete_twitter_browser_takeover(
    data: TwitterBrowserTakeoverRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from app.services.twitter_browser import check_browser_session_health, complete_manual_browser_login
    from app.services.twitter_twikit import reset_twitter_twikit

    try:
        status = await complete_manual_browser_login()
        browser_username = (status.get("username") or data.username or "").strip().lstrip("@")
        browser_email = (data.email or "").strip() or None
        browser_password = (data.password or "").strip() or None

        credentials = [
            ("twitter_username", browser_username),
            ("twitter_email", browser_email or ""),
        ]
        if browser_password:
            credentials.append(("twitter_password", browser_password))

        for key, value in credentials:
            await _upsert_setting(db, key, value)

        account_result = await db.execute(select(TwitterAccount).where(TwitterAccount.username == browser_username))
        existing_account = account_result.scalar_one_or_none()
        if existing_account:
            existing_account.account_key = existing_account.account_key or browser_username
            existing_account.username = browser_username
            existing_account.email = browser_email
            if browser_password:
                existing_account.password = browser_password
            existing_account.last_login_status = "manual_browser"
            existing_account.last_login_message = "人工接管 Browser 登录成功"
            await _set_active_twitter_account(db, existing_account)
        else:
            account = TwitterAccount(
                account_key=browser_username,
                username=browser_username,
                email=browser_email,
                password=browser_password,
                last_login_status="manual_browser",
                last_login_message="人工接管 Browser 登录成功",
            )
            db.add(account)
            await db.flush()
            await _set_active_twitter_account(db, account)

        await db.commit()
        sync_global_cookie_to_account(browser_username)
        reset_twitter_twikit()
        session_health = await check_browser_session_health()

        return TwitterBrowserTakeoverResponse(
            success=True,
            message=f"人工接管登录已完成，Browser 会话已保存并设为当前账号。{session_health.get('summary')}",
            username=browser_username,
            account_key=browser_username,
            ready=bool(status.get("ready")),
            manual_login_active=bool(status.get("manual_login_active")),
            vnc_url=_build_browser_takeover_url(request),
            updated_at=status.get("updated_at"),
            session_health=session_health,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "完成人工接管登录失败"))


@router.post("/twitter-browser-takeover/cancel", response_model=TwitterBrowserTakeoverResponse)
async def cancel_twitter_browser_takeover(request: Request):
    from app.services.twitter_browser import cancel_manual_browser_login

    try:
        await cancel_manual_browser_login()
        return TwitterBrowserTakeoverResponse(
            success=True,
            message="已关闭人工接管浏览器",
            ready=False,
            manual_login_active=False,
            vnc_url=_build_browser_takeover_url(request),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "关闭人工接管浏览器失败"))


@router.post("/twitter-login-diagnostic")
async def get_twitter_login_diagnostic_post():
    return {
        "success": True,
        "diagnostic": _load_browser_login_diagnostic(),
    }


@router.get("/twitter-accounts", response_model=list[TwitterAccountResponse])
async def list_twitter_accounts(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(TwitterAccount).order_by(TwitterAccount.is_active.desc(), TwitterAccount.updated_at.desc()))
        items = result.scalars().all()
        return [_serialize_twitter_account(item) for item in items]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载 Twitter 账号矩阵失败"))


@router.post("/twitter-accounts", response_model=TwitterAccountResponse)
async def create_or_update_twitter_account(
    data: TwitterAccountUpsertRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        normalized_key = (data.account_key or "").strip()
        normalized_username = (data.username or "").strip().lstrip("@")
        normalized_email = (data.email or "").strip() or None
        normalized_password = (data.password or "").strip() or None

        if not normalized_key:
            raise HTTPException(status_code=400, detail="账号标识不能为空")
        if not normalized_username:
            raise HTTPException(status_code=400, detail="用户名不能为空")

        result = await db.execute(select(TwitterAccount).where(TwitterAccount.account_key == normalized_key))
        account = result.scalar_one_or_none()

        if account:
            account.username = normalized_username
            account.email = normalized_email
            if normalized_password:
                account.password = normalized_password
        else:
            account = TwitterAccount(
                account_key=normalized_key,
                username=normalized_username,
                email=normalized_email,
                password=normalized_password,
                is_active=False,
            )
            db.add(account)
            await db.flush()

        if data.is_active:
            await _set_active_twitter_account(db, account)
            if not sync_account_cookie_to_global(account.account_key) and os.path.exists(COOKIE_FILE):
                os.remove(COOKIE_FILE)

        await db.commit()
        await db.refresh(account)
        return _serialize_twitter_account(account)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "保存 Twitter 账号失败"))


@router.post("/twitter-accounts/{account_id}/activate", response_model=TwitterAccountResponse)
async def activate_twitter_account(account_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(TwitterAccount).where(TwitterAccount.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise HTTPException(status_code=404, detail="未找到目标 Twitter 账号")

        await _set_active_twitter_account(db, account)
        if not sync_account_cookie_to_global(account.account_key) and os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        await db.commit()
        await db.refresh(account)
        return _serialize_twitter_account(account)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "切换活跃账号失败"))


@router.post("/twitter-accounts/{account_id}/health-check", response_model=TwitterAccountHealthCheckResponse)
async def check_twitter_account_health(account_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(TwitterAccount).where(TwitterAccount.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise HTTPException(status_code=404, detail="未找到目标 Twitter 账号")
        return await _check_twitter_account_health(account)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "检测 Twitter 账号可用性失败"))


@router.delete("/twitter-accounts/{account_id}")
async def delete_twitter_account(account_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(TwitterAccount).where(TwitterAccount.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise HTTPException(status_code=404, detail="未找到目标 Twitter 账号")

        was_active = bool(account.is_active)
        await db.delete(account)
        await db.flush()

        if was_active:
            fallback_result = await db.execute(select(TwitterAccount).order_by(TwitterAccount.updated_at.desc()))
            fallback = fallback_result.scalars().first()
            await _set_active_twitter_account(db, fallback)
            if fallback:
                sync_account_cookie_to_global(fallback.account_key)
            elif os.path.exists(COOKIE_FILE):
                os.remove(COOKIE_FILE)

        await db.commit()
        return {
            "success": True,
            "message": f"已删除账号 @{account.username}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "删除 Twitter 账号失败"))


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

    account_result = await db.execute(select(TwitterAccount).where(TwitterAccount.username == data.username))
    existing_account = account_result.scalar_one_or_none()

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

        if existing_account:
            existing_account.account_key = existing_account.account_key or data.username
            existing_account.username = data.username
            existing_account.email = data.email
            existing_account.password = password
            existing_account.last_login_status = "success"
            existing_account.last_login_message = "Browser 模式登录成功"
            await _set_active_twitter_account(db, existing_account)
        else:
            account = TwitterAccount(
                account_key=data.username,
                username=data.username,
                email=data.email,
                password=password,
                last_login_status="success",
                last_login_message="Browser 模式登录成功",
            )
            db.add(account)
            await db.flush()
            await _set_active_twitter_account(db, account)

        await db.commit()
        sync_global_cookie_to_account(data.username)
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

        if existing_account:
            existing_account.username = data.username
            existing_account.email = data.email
            if data.password:
                existing_account.password = data.password
            existing_account.last_login_status = "cookie"
            existing_account.last_login_message = "Cookie 模式已启用"
            await _set_active_twitter_account(db, existing_account)
        else:
            account = TwitterAccount(
                account_key=data.username,
                username=data.username,
                email=data.email,
                password=(data.password or None),
                last_login_status="cookie",
                last_login_message="Cookie 模式已启用",
            )
            db.add(account)
            await db.flush()
            await _set_active_twitter_account(db, account)

        await db.commit()
        sync_global_cookie_to_account(data.username)
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

        if existing_account:
            existing_account.username = data.username
            existing_account.email = data.email
            if data.password:
                existing_account.password = data.password
            existing_account.last_login_status = "success"
            existing_account.last_login_message = "Twikit 登录成功"
            await _set_active_twitter_account(db, existing_account)
        else:
            account = TwitterAccount(
                account_key=data.username,
                username=data.username,
                email=data.email,
                password=(data.password or password),
                last_login_status="success",
                last_login_message="Twikit 登录成功",
            )
            db.add(account)
            await db.flush()
            await _set_active_twitter_account(db, account)

        await db.commit()
        sync_global_cookie_to_account(data.username)

        # 重置全局单例，下次使用时会用新的 cookie
        reset_twitter_twikit()

        return TwitterLoginResponse(
            success=True,
            message="登录成功",
            username=me["username"]
        )
    except Exception as e:
        if existing_account:
            existing_account.last_login_status = "error"
            existing_account.last_login_message = str(e)
            await db.commit()
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
            message="LLM 连接成功",
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
