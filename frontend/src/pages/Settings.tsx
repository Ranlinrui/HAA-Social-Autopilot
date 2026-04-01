import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, CheckCircle, XCircle, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { formatTwitterActionError, logClientError, settingsApi } from '@/services/api'
import TwitterCookieManager from '@/components/TwitterCookieManager'
import { InlineNotice } from '@/components/InlineNotice'
import { TwitterRiskAccountPanel, TwitterRiskBanner, type TwitterRiskAccountLike, type TwitterRiskStateLike } from '@/components/TwitterRiskStatus'

interface TestResult {
  success: boolean
  message: string
  detail?: string
}

interface PageMessage {
  tone: 'error' | 'success' | 'info'
  title: string
  message: string
}

const AUTH_REFRESH_ERROR_TITLE = '认证状态刷新失败'

interface CookieStatus {
  configured: boolean
  is_valid?: boolean
  is_expired?: boolean
  account_name?: string
  username?: string
  message?: string
  validation_mode?: string
}

interface TwitterAuthState extends TwitterRiskStateLike {
  feature: string
  selected_mode: string
  default_mode: string
  cookie_configured: boolean
  cookie_validation_mode?: string
  cookie_username?: string
  configured_username?: string
  active_username?: string
  last_risk_event_at?: string
}

interface TwitterRiskAccount extends TwitterRiskAccountLike {
  is_persisted: boolean
  is_active_display_only: boolean
  last_risk_event_at?: string
}

interface TwitterMatrixAccount {
  id: number
  account_key: string
  username: string
  email?: string
  is_active: boolean
  password_saved: boolean
  cookie_ready: boolean
  browser_session_ready: boolean
  automation_ready: boolean
  last_login_status?: string
  last_login_message?: string
  created_at: string
  updated_at: string
}

interface TwitterMatrixAccountHealthCheck {
  success: boolean
  account_key: string
  username: string
  cookie_ready: boolean
  browser_session_ready: boolean
  automation_ready: boolean
  twikit_ok: boolean
  twikit_message: string
  browser_message: string
  checked_at: string
}

interface TwitterBrowserSession {
  success: boolean
  message: string
  username?: string
  ready: boolean
  updated_at?: string
}

interface TwitterBrowserTakeover {
  success: boolean
  message: string
  username?: string
  account_key?: string
  ready: boolean
  manual_login_active: boolean
  vnc_url?: string
  updated_at?: string
  session_health?: {
    ok: boolean
    summary: string
    checked_at?: string
    checks: Array<{
      name: string
      ok: boolean
      detail: string
    }>
  }
}

const twitterFeatureModes = [
  { key: 'twitter_mode_test_connection', label: '连接测试' },
  { key: 'twitter_mode_publish', label: '发帖' },
  { key: 'twitter_mode_search', label: '搜索' },
  { key: 'twitter_mode_reply', label: '回复' },
  { key: 'twitter_mode_retweet', label: '转推' },
  { key: 'twitter_mode_quote', label: '引用' },
  { key: 'twitter_mode_mentions', label: '提及读取' },
  { key: 'twitter_mode_tweet_lookup', label: '推文查询' },
] as const

const autoActionSettingsMeta = [
  {
    key: 'auto_action_min_interval_seconds',
    label: '最小动作间隔（秒）',
    description: '同一账号两次自动动作之间至少等待多久。越小越激进。',
    min: 10,
  },
  {
    key: 'auto_reply_hourly_limit',
    label: '每小时自动回复上限',
    description: '单个账号每小时最多自动回复多少次。',
    min: 1,
  },
  {
    key: 'auto_retweet_hourly_limit',
    label: '每小时自动转推上限',
    description: '单个账号每小时最多自动转推多少次。',
    min: 0,
  },
  {
    key: 'auto_action_daily_limit',
    label: '24 小时自动动作总上限',
    description: '单个账号 24 小时内所有自动动作的总上限。',
    min: 1,
  },
] as const

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [, setSaving] = useState(false)
  const [twitterTest, setTwitterTest] = useState<TestResult | null>(null)
  const [llmTest, setLlmTest] = useState<TestResult | null>(null)
  const [testingTwitter, setTestingTwitter] = useState(false)
  const [testingLLM, setTestingLLM] = useState(false)
  const [twitterUsername, setTwitterUsername] = useState('')
  const [twitterEmail, setTwitterEmail] = useState('')
  const [twitterPassword, setTwitterPassword] = useState('')
  const [twitterPasswordSaved, setTwitterPasswordSaved] = useState(false)
  const [loggingIn, setLoggingIn] = useState(false)
  const [loginResult, setLoginResult] = useState<TestResult | null>(null)
  const [cookieStatus, setCookieStatus] = useState<CookieStatus | null>(null)
  const [authState, setAuthState] = useState<TwitterAuthState | null>(null)
  const [riskAccounts, setRiskAccounts] = useState<TwitterRiskAccount[]>([])
  const [twitterAccounts, setTwitterAccounts] = useState<TwitterMatrixAccount[]>([])
  const [browserSession, setBrowserSession] = useState<TwitterBrowserSession | null>(null)
  const [browserTakeover, setBrowserTakeover] = useState<TwitterBrowserTakeover | null>(null)
  const [resettingRiskAccount, setResettingRiskAccount] = useState<string | null>(null)
  const [savingMatrixAccount, setSavingMatrixAccount] = useState(false)
  const [activatingAccountId, setActivatingAccountId] = useState<number | null>(null)
  const [deletingAccountId, setDeletingAccountId] = useState<number | null>(null)
  const [syncingBrowserSession, setSyncingBrowserSession] = useState(false)
  const [startingBrowserTakeover, setStartingBrowserTakeover] = useState(false)
  const [completingBrowserTakeover, setCompletingBrowserTakeover] = useState(false)
  const [cancelingBrowserTakeover, setCancelingBrowserTakeover] = useState(false)
  const [pageMessage, setPageMessage] = useState<PageMessage | null>(null)
  const [applyingModePreset, setApplyingModePreset] = useState<string | null>(null)
  const [checkingAccountId, setCheckingAccountId] = useState<number | null>(null)
  const [accountHealthChecks, setAccountHealthChecks] = useState<Record<number, TwitterMatrixAccountHealthCheck>>({})
  const [guideAccountId, setGuideAccountId] = useState<number | null>(null)
  const [autoActionSettings, setAutoActionSettings] = useState<Record<string, string>>({})
  const [savingAutoActionSettings, setSavingAutoActionSettings] = useState(false)

  const activeCookieUsername = cookieStatus?.username || cookieStatus?.account_name || ''
  const hasAccountMismatch = Boolean(
    activeCookieUsername &&
    twitterUsername &&
    activeCookieUsername !== twitterUsername
  )

  useEffect(() => {
    loadSettings()
  }, [])

  useEffect(() => {
    setAutoActionSettings((current) => {
      const next = { ...current }
      for (const item of autoActionSettingsMeta) {
        next[item.key] = settings[item.key] || ''
      }
      return next
    })
  }, [settings])

  const refreshAuthState = useCallback(async () => {
    const [next, accounts] = await Promise.allSettled([
      settingsApi.getTwitterAuthState(),
      settingsApi.getTwitterRiskAccounts(),
    ])

    const nextAuthState = next.status === 'fulfilled' ? next.value : null
    const nextRiskAccounts = accounts.status === 'fulfilled' ? accounts.value : []

    setAuthState(nextAuthState)
    setRiskAccounts(nextRiskAccounts)

    if (next.status === 'fulfilled' && accounts.status === 'fulfilled') {
      setPageMessage((current) =>
        current?.title === AUTH_REFRESH_ERROR_TITLE ? null : current
      )
    } else if (next.status === 'rejected' || accounts.status === 'rejected') {
      const firstError = next.status === 'rejected'
        ? next.reason
        : accounts.status === 'rejected'
          ? accounts.reason
          : null
      const fallbackMessage =
        next.status === 'fulfilled' || accounts.status === 'fulfilled'
          ? '认证状态部分刷新失败，后端仍可访问，但部分接口本次未成功返回。'
          : '认证状态加载失败'
      setPageMessage({
        tone: 'error',
        title: AUTH_REFRESH_ERROR_TITLE,
        message: formatTwitterActionError(firstError, fallbackMessage),
      })
    }

    return nextAuthState
  }, [])

  const loadSettings = async () => {
    let hasFailure = false

    try {
      setPageMessage(null)
      const [res, authState, accounts, matrixAccountsResult, browserSessionResult, browserTakeoverResult] = await Promise.allSettled([
        settingsApi.get(),
        settingsApi.getTwitterAuthState(),
        settingsApi.getTwitterRiskAccounts(),
        settingsApi.getTwitterAccounts(),
        settingsApi.getTwitterBrowserSession(),
        settingsApi.getTwitterBrowserTakeover(),
      ])

      if (res.status === 'fulfilled') {
        setSettings(res.value.settings)
        if (res.value.settings.twitter_username) setTwitterUsername(res.value.settings.twitter_username)
        if (res.value.settings.twitter_email) setTwitterEmail(res.value.settings.twitter_email)
        if (res.value.settings.twitter_password_saved) setTwitterPasswordSaved(true)
      } else {
        hasFailure = true
      }

      const nextAuthState = authState.status === 'fulfilled' ? authState.value : null
      const nextRiskAccounts = accounts.status === 'fulfilled' ? accounts.value : []

      if (authState.status === 'fulfilled') {
        setAuthState(nextAuthState)
      } else {
        hasFailure = true
      }

      if (accounts.status === 'fulfilled') {
        setRiskAccounts(nextRiskAccounts)
      } else {
        hasFailure = true
      }

      if (matrixAccountsResult.status === 'fulfilled') {
        setTwitterAccounts(matrixAccountsResult.value)
      } else {
        hasFailure = true
      }

      if (browserSessionResult.status === 'fulfilled') {
        setBrowserSession(browserSessionResult.value)
      } else {
        hasFailure = true
      }

      if (browserTakeoverResult.status === 'fulfilled') {
        setBrowserTakeover(browserTakeoverResult.value)
      } else {
        hasFailure = true
      }

      if (nextAuthState?.cookie_configured) {
        setCookieStatus({
          configured: true,
          username: nextAuthState.cookie_username || nextAuthState.active_username,
          account_name: nextAuthState.cookie_username || nextAuthState.active_username,
          validation_mode: nextAuthState.cookie_validation_mode,
          is_valid: true,
        })
        if (nextAuthState.active_username) {
          setTwitterUsername(nextAuthState.active_username)
          setSettings((current) => ({ ...current, twitter_username: nextAuthState.active_username || '' }))
        }
      }

      if (hasFailure) {
        const firstError =
          res.status === 'rejected'
            ? res.reason
            : authState.status === 'rejected'
              ? authState.reason
              : accounts.status === 'rejected'
                ? accounts.reason
                : matrixAccountsResult.status === 'rejected'
                  ? matrixAccountsResult.reason
                  : browserSessionResult.status === 'rejected'
                    ? browserSessionResult.reason
                    : browserTakeoverResult.status === 'rejected'
                      ? browserTakeoverResult.reason
                  : null
        setPageMessage({
          tone: 'error',
          title: '设置页部分数据加载失败',
          message: formatTwitterActionError(firstError, '部分设置数据加载失败'),
        })
      }
    } catch (error) {
      logClientError('Settings.loadSettings', error)
      setPageMessage({
        tone: 'error',
        title: '设置页加载失败',
        message: formatTwitterActionError(error, '设置数据加载失败'),
      })
    } finally {
      setLoading(false)
    }
  }

  const reloadTwitterAccounts = useCallback(async () => {
    const accounts = await settingsApi.getTwitterAccounts()
    setTwitterAccounts(accounts)
    return accounts
  }, [])

  const reloadBrowserSession = useCallback(async () => {
    const next = await settingsApi.getTwitterBrowserSession()
    setBrowserSession(next)
    return next
  }, [])

  const reloadBrowserTakeover = useCallback(async () => {
    const next = await settingsApi.getTwitterBrowserTakeover()
    setBrowserTakeover((current) => ({
      ...next,
      session_health: next.session_health ?? current?.session_health,
    }))
    return next
  }, [])

  const handleSave = async (key: string, value: string) => {
    setSaving(true)
    try {
      await settingsApi.update(key, value)
      setSettings({ ...settings, [key]: value })
      setPageMessage({
        tone: 'success',
        title: '设置已更新',
        message: `配置项 ${key} 已保存。`,
      })
    } catch (error) {
      logClientError('Settings.handleSave', error)
      setPageMessage({
        tone: 'error',
        title: '保存设置失败',
        message: formatTwitterActionError(error, '保存设置失败'),
      })
    } finally {
      setSaving(false)
    }
  }

  const handleCookieStatusChange = useCallback((status: CookieStatus | null) => {
    setCookieStatus(status)
    if (!status?.configured) {
      void Promise.all([refreshAuthState(), reloadBrowserSession(), reloadBrowserTakeover()])
      setTwitterUsername('')
      setSettings((current) => ({ ...current, twitter_username: '' }))
      setLoginResult(null)
      setTwitterTest(null)
      return
    }
    void Promise.all([refreshAuthState(), reloadBrowserSession(), reloadBrowserTakeover()])
    if (status.username || status.account_name) {
      const activeUsername = status.username || status.account_name || ''
      setTwitterUsername(activeUsername)
      setSettings((current) => ({ ...current, twitter_username: activeUsername }))
    }
  }, [refreshAuthState, reloadBrowserSession, reloadBrowserTakeover])

  const handleTwitterLogin = async () => {
    if (!twitterUsername || !twitterEmail) return
    if (!twitterPassword && !twitterPasswordSaved) return
    setLoggingIn(true)
    setLoginResult(null)
    try {
      const res = await settingsApi.twitterLogin(twitterUsername, twitterEmail, twitterPassword || undefined)
      setLoginResult({
        success: res.success,
        message: res.message,
        detail: res.username ? `@${res.username}` : undefined,
      })
      if (res.success) {
        setTwitterPasswordSaved(true)
        setTwitterPassword('')
        await Promise.all([refreshAuthState(), reloadTwitterAccounts(), reloadBrowserSession(), reloadBrowserTakeover()])
      }
    } catch (error) {
      setLoginResult({
        success: false,
        message: formatTwitterActionError(error, '登录请求失败'),
      })
    } finally {
      setLoggingIn(false)
    }
  }

  const testTwitterConnection = async () => {
    setTestingTwitter(true)
    setTwitterTest(null)
    try {
      const res = await settingsApi.testTwitter()
      await Promise.all([refreshAuthState(), reloadBrowserSession(), reloadBrowserTakeover()])
      setTwitterTest({
        success: res.success,
        message: res.message,
        detail: res.username ? `@${res.username}` : undefined,
      })
    } catch (error) {
      setTwitterTest({
        success: false,
        message: formatTwitterActionError(error, '连接失败'),
      })
    } finally {
      setTestingTwitter(false)
    }
  }

  const testLLMConnection = async () => {
    setTestingLLM(true)
    setLlmTest(null)
    try {
      const res = await settingsApi.testLLM()
      setLlmTest({
        success: res.success,
        message: res.message,
        detail: res.model,
      })
    } catch (error) {
      setLlmTest({
        success: false,
        message: formatTwitterActionError(error, '连接失败'),
      })
    } finally {
      setTestingLLM(false)
    }
  }

  const handleResetRiskAccount = async (accountKey: string) => {
    setResettingRiskAccount(accountKey)
    try {
      const result = await settingsApi.resetTwitterRiskAccount(accountKey)
      await refreshAuthState()
      setPageMessage({
        tone: result.removed ? 'success' : 'info',
        title: result.removed ? '风控状态已重置' : '无需重置',
        message: result.message,
      })
    } catch (error) {
      logClientError('Settings.handleResetRiskAccount', error)
      setPageMessage({
        tone: 'error',
        title: '重置风控失败',
        message: formatTwitterActionError(error, '重置风控失败'),
      })
    } finally {
      setResettingRiskAccount(null)
    }
  }

  const handleSaveMatrixAccount = async (makeActive = false) => {
    if (!twitterUsername.trim()) return
    setSavingMatrixAccount(true)
    try {
      const payload = {
        account_key: twitterUsername.trim().replace(/^@/, ''),
        username: twitterUsername.trim().replace(/^@/, ''),
        email: twitterEmail.trim() || undefined,
        password: twitterPassword || undefined,
        is_active: makeActive,
      }
      await settingsApi.saveTwitterAccount(payload)
      await reloadTwitterAccounts()
      if (makeActive) {
        await refreshAuthState()
      }
      if (twitterPassword) {
        setTwitterPasswordSaved(true)
        setTwitterPassword('')
      }
      setPageMessage({
        tone: 'success',
        title: makeActive ? '账号已保存并激活' : '账号已保存',
        message: `账号 @${payload.username} 已加入账号矩阵。`,
      })
    } catch (error) {
      logClientError('Settings.handleSaveMatrixAccount', error)
      setPageMessage({
        tone: 'error',
        title: '保存账号失败',
        message: formatTwitterActionError(error, '保存账号失败'),
      })
    } finally {
      setSavingMatrixAccount(false)
    }
  }

  const openExternalSignupPage = () => {
    window.open('https://x.com/i/flow/signup', '_blank', 'noopener,noreferrer')
  }

  const handlePrepareRegistrationAccount = async () => {
    if (!twitterUsername.trim()) return
    setSavingMatrixAccount(true)
    try {
      await settingsApi.saveTwitterAccount({
        account_key: twitterUsername.trim().replace(/^@/, ''),
        username: twitterUsername.trim().replace(/^@/, ''),
        email: twitterEmail.trim() || undefined,
        password: twitterPassword || undefined,
        is_active: false,
      })
      await reloadTwitterAccounts()
      setPageMessage({
        tone: 'success',
        title: '待接入账号已保存',
        message: `账号 @${twitterUsername.trim().replace(/^@/, '')} 已保存到矩阵。请在你自己的浏览器完成注册/登录，然后回到这里导入 Cookie。`,
      })
    } catch (error) {
      logClientError('Settings.handlePrepareRegistrationAccount', error)
      setPageMessage({
        tone: 'error',
        title: '保存待接入账号失败',
        message: formatTwitterActionError(error, '保存待接入账号失败'),
      })
    } finally {
      setSavingMatrixAccount(false)
    }
  }

  const handleCompleteRegistrationAccess = async () => {
    if (!twitterUsername.trim()) return
    setSavingMatrixAccount(true)
    try {
      await settingsApi.saveTwitterAccount({
        account_key: twitterUsername.trim().replace(/^@/, ''),
        username: twitterUsername.trim().replace(/^@/, ''),
        email: twitterEmail.trim() || undefined,
        password: twitterPassword || undefined,
        is_active: true,
      })
      await Promise.all([reloadTwitterAccounts(), refreshAuthState(), reloadBrowserSession(), reloadBrowserTakeover()])
      setPageMessage({
        tone: 'success',
        title: '注册账号已接入矩阵',
        message: `账号 @${twitterUsername.trim().replace(/^@/, '')} 已设为活跃。若你刚导入的是该账号 Cookie，它现在就能参与后续执行链路。`,
      })
      if (twitterPassword) {
        setTwitterPasswordSaved(true)
        setTwitterPassword('')
      }
    } catch (error) {
      logClientError('Settings.handleCompleteRegistrationAccess', error)
      setPageMessage({
        tone: 'error',
        title: '注册后接入矩阵失败',
        message: formatTwitterActionError(error, '注册后接入矩阵失败'),
      })
    } finally {
      setSavingMatrixAccount(false)
    }
  }

  const handleActivateMatrixAccount = async (account: TwitterMatrixAccount) => {
    setActivatingAccountId(account.id)
    try {
      await settingsApi.activateTwitterAccount(account.id)
      await Promise.all([reloadTwitterAccounts(), refreshAuthState()])
      setTwitterUsername(account.username)
      setTwitterEmail(account.email || '')
      setTwitterPassword('')
      setTwitterPasswordSaved(account.password_saved)
      setPageMessage({
        tone: 'success',
        title: '活跃账号已切换',
        message: `当前活跃账号已切换为 @${account.username}。`,
      })
    } catch (error) {
      logClientError('Settings.handleActivateMatrixAccount', error)
      setPageMessage({
        tone: 'error',
        title: '切换账号失败',
        message: formatTwitterActionError(error, '切换活跃账号失败'),
      })
    } finally {
      setActivatingAccountId(null)
    }
  }

  const handleDeleteMatrixAccount = async (account: TwitterMatrixAccount) => {
    setDeletingAccountId(account.id)
    try {
      const result = await settingsApi.deleteTwitterAccount(account.id)
      await Promise.all([reloadTwitterAccounts(), refreshAuthState()])
      setPageMessage({
        tone: 'success',
        title: '账号已删除',
        message: result.message,
      })
    } catch (error) {
      logClientError('Settings.handleDeleteMatrixAccount', error)
      setPageMessage({
        tone: 'error',
        title: '删除账号失败',
        message: formatTwitterActionError(error, '删除账号失败'),
      })
    } finally {
      setDeletingAccountId(null)
    }
  }

  const handleCheckMatrixAccountHealth = async (account: TwitterMatrixAccount) => {
    setCheckingAccountId(account.id)
    try {
      const result = await settingsApi.checkTwitterAccountHealth(account.id)
      setAccountHealthChecks((current) => ({ ...current, [account.id]: result }))
      await reloadTwitterAccounts()
      setPageMessage({
        tone: result.twikit_ok || result.browser_session_ready ? 'success' : 'info',
        title: '账号检测已完成',
        message: `@${account.username}：${result.twikit_message}；${result.browser_message}`,
      })
    } catch (error) {
      logClientError('Settings.handleCheckMatrixAccountHealth', error)
      setPageMessage({
        tone: 'error',
        title: '账号检测失败',
        message: formatTwitterActionError(error, '检测账号可用性失败'),
      })
    } finally {
      setCheckingAccountId(null)
    }
  }

  const handleLoadMatrixAccount = (account: TwitterMatrixAccount) => {
    setTwitterUsername(account.username)
    setTwitterEmail(account.email || '')
    setTwitterPassword('')
    setTwitterPasswordSaved(account.password_saved)
    setPageMessage({
      tone: 'info',
      title: '账号已载入表单',
      message: `已载入 @${account.username}，你可以继续登录、更新密码或切换活跃账号。`,
    })
  }

  const handleShowAccountGuide = (account: TwitterMatrixAccount) => {
    setGuideAccountId((current) => current === account.id ? null : account.id)
    setTwitterUsername(account.username)
    setTwitterEmail(account.email || '')
    setTwitterPassword('')
    setTwitterPasswordSaved(account.password_saved)
  }

  const handleSyncBrowserSession = async () => {
    setSyncingBrowserSession(true)
    try {
      const result = await settingsApi.syncTwitterBrowserSession()
      setBrowserSession(result)
      await Promise.all([refreshAuthState(), reloadBrowserTakeover()])
      setPageMessage({
        tone: 'success',
        title: 'Browser 会话已同步',
        message: result.message,
      })
    } catch (error) {
      logClientError('Settings.handleSyncBrowserSession', error)
      setPageMessage({
        tone: 'error',
        title: '同步 Browser 会话失败',
        message: formatTwitterActionError(error, '同步 Browser 会话失败'),
      })
    } finally {
      setSyncingBrowserSession(false)
    }
  }

  const openBrowserTakeoverWindow = (takeover: TwitterBrowserTakeover | null) => {
    if (!takeover?.vnc_url) return
    window.open(takeover.vnc_url, '_blank', 'noopener,noreferrer')
  }

  const handleStartBrowserTakeover = async () => {
    if (!twitterUsername.trim()) return
    setStartingBrowserTakeover(true)
    try {
      const result = await settingsApi.startTwitterBrowserTakeover({
        username: twitterUsername.trim().replace(/^@/, ''),
        email: twitterEmail.trim() || undefined,
        password: twitterPassword || undefined,
      })
      setBrowserTakeover(result)
      setPageMessage({
        tone: 'info',
        title: '人工接管浏览器已启动',
        message: result.message,
      })
      openBrowserTakeoverWindow(result)
    } catch (error) {
      logClientError('Settings.handleStartBrowserTakeover', error)
      setPageMessage({
        tone: 'error',
        title: '启动人工接管失败',
        message: formatTwitterActionError(error, '启动人工接管浏览器失败'),
      })
    } finally {
      setStartingBrowserTakeover(false)
    }
  }

  const handleCompleteBrowserTakeover = async () => {
    if (!twitterUsername.trim()) return
    setCompletingBrowserTakeover(true)
    try {
      const result = await settingsApi.completeTwitterBrowserTakeover({
        username: twitterUsername.trim().replace(/^@/, ''),
        email: twitterEmail.trim() || undefined,
        password: twitterPassword || undefined,
      })
      setBrowserTakeover(result)
      await Promise.all([refreshAuthState(), reloadBrowserSession(), reloadTwitterAccounts()])
      setPageMessage({
        tone: 'success',
        title: '人工接管登录已完成',
        message: result.message,
      })
    } catch (error) {
      logClientError('Settings.handleCompleteBrowserTakeover', error)
      setPageMessage({
        tone: 'error',
        title: '完成人工接管失败',
        message: formatTwitterActionError(error, '完成人工接管登录失败'),
      })
    } finally {
      setCompletingBrowserTakeover(false)
    }
  }

  const handleCancelBrowserTakeover = async () => {
    setCancelingBrowserTakeover(true)
    try {
      const result = await settingsApi.cancelTwitterBrowserTakeover()
      setBrowserTakeover(result)
      setPageMessage({
        tone: 'info',
        title: '人工接管已关闭',
        message: result.message,
      })
    } catch (error) {
      logClientError('Settings.handleCancelBrowserTakeover', error)
      setPageMessage({
        tone: 'error',
        title: '关闭人工接管失败',
        message: formatTwitterActionError(error, '关闭人工接管浏览器失败'),
      })
    } finally {
      setCancelingBrowserTakeover(false)
    }
  }

  const handleSaveAutoActionSettings = async () => {
    setSavingAutoActionSettings(true)
    try {
      for (const item of autoActionSettingsMeta) {
        const rawValue = String(autoActionSettings[item.key] || '').trim()
        const parsed = Number(rawValue)
        if (!Number.isFinite(parsed) || parsed < item.min) {
          throw new Error(`${item.label} 不能小于 ${item.min}`)
        }
      }

      for (const item of autoActionSettingsMeta) {
        const value = String(Math.floor(Number(autoActionSettings[item.key])))
        await settingsApi.update(item.key, value)
      }

      setSettings((current) => {
        const next = { ...current }
        for (const item of autoActionSettingsMeta) {
          next[item.key] = String(Math.floor(Number(autoActionSettings[item.key])))
        }
        return next
      })

      setPageMessage({
        tone: 'success',
        title: '自动互动频率已更新',
        message: '新的回复/转推频率限制已保存并会用于后续自动任务。',
      })
    } catch (error) {
      logClientError('Settings.handleSaveAutoActionSettings', error)
      setPageMessage({
        tone: 'error',
        title: '保存自动互动频率失败',
        message: formatTwitterActionError(error, '保存自动互动频率失败'),
      })
    } finally {
      setSavingAutoActionSettings(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">系统设置</h2>
        <p className="text-muted-foreground">配置Twitter和LLM连接参数</p>
      </div>

      {pageMessage && (
        <InlineNotice
          tone={pageMessage.tone}
          title={pageMessage.title}
          message={pageMessage.message}
          dismissible
          autoHideMs={pageMessage.tone === 'error' ? undefined : 4000}
          onClose={() => setPageMessage(null)}
        />
      )}

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Twitter配置</CardTitle>
            <CardDescription>
              配置 Twitter 执行模式与认证方式。当前建议优先使用 Cookie 导入，Browser 密码登录仅作为补充排障手段。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4">
              <div>
                <label className="text-sm font-medium">运行模式预设</label>
                <div className="grid gap-3 mt-2 md:grid-cols-2">
                  <div className="rounded-lg border px-4 py-3">
                    <div className="font-medium">低成本模式</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      几乎所有功能走 Twikit，Browser 主要用于登录接管与会话维护，适合长期低流量运行。
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="mt-3"
                      onClick={async () => {
                        setApplyingModePreset('low_cost')
                        try {
                          const result = await settingsApi.applyTwitterModePreset('low_cost')
                          await loadSettings()
                          setPageMessage({
                            tone: 'success',
                            title: '已切换到低成本模式',
                            message: result.message,
                          })
                        } catch (error) {
                          setPageMessage({
                            tone: 'error',
                            title: '切换低成本模式失败',
                            message: formatTwitterActionError(error, '切换低成本模式失败'),
                          })
                        } finally {
                          setApplyingModePreset(null)
                        }
                      }}
                      disabled={applyingModePreset !== null}
                    >
                      {applyingModePreset === 'low_cost' ? '切换中' : '启用低成本模式'}
                    </Button>
                  </div>
                  <div className="rounded-lg border px-4 py-3">
                    <div className="font-medium">高可用模式</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      搜索、提及和推文读取优先走 Browser，写入保留 Twikit，适合更重视读取稳定性的场景。
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="mt-3"
                      onClick={async () => {
                        setApplyingModePreset('high_availability')
                        try {
                          const result = await settingsApi.applyTwitterModePreset('high_availability')
                          await loadSettings()
                          setPageMessage({
                            tone: 'success',
                            title: '已切换到高可用模式',
                            message: result.message,
                          })
                        } catch (error) {
                          setPageMessage({
                            tone: 'error',
                            title: '切换高可用模式失败',
                            message: formatTwitterActionError(error, '切换高可用模式失败'),
                          })
                        } finally {
                          setApplyingModePreset(null)
                        }
                      }}
                      disabled={applyingModePreset !== null}
                    >
                      {applyingModePreset === 'high_availability' ? '切换中' : '启用高可用模式'}
                    </Button>
                  </div>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium">执行模式</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm mt-1"
                  value={settings.twitter_publish_mode || 'twikit'}
                  onChange={(e) => handleSave('twitter_publish_mode', e.target.value)}
                >
                  <option value="twikit">Twikit 模式 (兼容/当前可用)</option>
                  <option value="browser">Browser 模式 (长期主模式，开发中)</option>
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  Twikit 模式保留现有低成本链路；Browser 模式用于后续长期替代方案，当前仍在开发中。
                </p>
              </div>

              <div className="pt-4 border-t space-y-3">
                <div>
                  <label className="text-sm font-medium">功能级模式路由</label>
                  <p className="text-xs text-muted-foreground mt-1">
                    先保持默认全走 Twikit，后面可以按功能逐步切到 Browser 模式。
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {twitterFeatureModes.map((item) => (
                    <div key={item.key}>
                      <label className="text-xs font-medium text-muted-foreground">{item.label}</label>
                      <select
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm mt-1"
                        value={settings[item.key] || 'twikit'}
                        onChange={(e) => handleSave(item.key, e.target.value)}
                      >
                        <option value="twikit">Twikit</option>
                        <option value="browser">Browser</option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t">
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <div className="font-medium">推荐认证顺序</div>
                  <div className="mt-1">
                    1. 先在下方导入 <code>auth_token</code> 和 <code>ct0</code>
                    2. 用“测试 Cookies”确认可用
                    3. 只有在 Cookie 不可用时，再尝试账号密码登录
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t space-y-3">
                <div>
                  <label className="text-sm font-medium">自动互动频率</label>
                  <p className="text-xs text-muted-foreground mt-1">
                    这里控制自动回复和自动转推的频率。调高可以更积极，调低更稳。即使这里调高，风控保护仍然会在异常情况下继续拦截。
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {autoActionSettingsMeta.map((item) => (
                    <div key={item.key}>
                      <label className="text-xs font-medium text-muted-foreground">{item.label}</label>
                      <Input
                        type="number"
                        min={item.min}
                        value={autoActionSettings[item.key] || ''}
                        onChange={(e) =>
                          setAutoActionSettings((current) => ({
                            ...current,
                            [item.key]: e.target.value,
                          }))
                        }
                        className="mt-1"
                      />
                      <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleSaveAutoActionSettings}
                    disabled={savingAutoActionSettings}
                  >
                    {savingAutoActionSettings ? '保存中' : '保存自动互动频率'}
                  </Button>
                  <div className="text-xs text-muted-foreground">
                    当前值：间隔 {settings.auto_action_min_interval_seconds || '240'} 秒，回复每小时 {settings.auto_reply_hourly_limit || '4'} 次，转推每小时 {settings.auto_retweet_hourly_limit || '2'} 次，24 小时总上限 {settings.auto_action_daily_limit || '12'} 次。
                  </div>
                </div>
              </div>

              <div className="pt-2">
                <TwitterCookieManager
                  onStatusChange={handleCookieStatusChange}
                  defaultAccountName={twitterUsername}
                  accountOptions={twitterAccounts.map((account) => ({
                    account_key: account.account_key,
                    username: account.username,
                  }))}
                />
              </div>

              <TwitterRiskBanner state={authState} />

              <TwitterRiskAccountPanel
                items={riskAccounts}
                activeUsername={authState?.active_username}
                resettingKey={resettingRiskAccount}
                onReset={handleResetRiskAccount}
              />

              <div className="pt-4 border-t space-y-3">
                <div>
                  <label className="text-sm font-medium">账号矩阵</label>
                  <p className="text-xs text-muted-foreground mt-1">
                    这里管理多账号池。活跃账号会同步到当前执行链路，方便后续扩成真正的多账号矩阵。
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    长期稳定方案不是在同一个浏览器里反复切号，而是为每个账号维护独立会话。至少要做到：一个账号对应一份独立 Cookie，最好再对应一份独立 Browser 会话。
                  </p>
                </div>
                {twitterAccounts.length === 0 ? (
                  <div className="rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">
                    还没有保存任何账号。你可以先在下方填写账号信息，再点“保存到矩阵”。
                  </div>
                ) : (
                  <div className="space-y-3">
                    {twitterAccounts.map((account) => {
                      const healthCheck = accountHealthChecks[account.id]
                      const showGuide = guideAccountId === account.id
                      return (
                      <div key={account.id} className={`rounded-lg border px-4 py-3 text-sm ${account.is_active ? 'border-emerald-300 bg-emerald-50/70' : 'border-border bg-background'}`}>
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                          <div className="space-y-1">
                            <div className="font-medium">
                              @{account.username}
                              <span className="ml-2 text-xs font-normal text-muted-foreground">标识: {account.account_key}</span>
                              {account.is_active && <span className="ml-2 text-xs text-emerald-700">当前活跃</span>}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {account.email || '未保存邮箱'}
                              {account.password_saved ? ' · 已保存密码' : ' · 未保存密码'}
                              {account.last_login_status ? ` · 最近状态: ${account.last_login_status}` : ''}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-xs">
                              <span className={`rounded-full px-2 py-0.5 ${account.cookie_ready ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                                {account.cookie_ready ? 'Cookie 就绪' : 'Cookie 未就绪'}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 ${account.browser_session_ready ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-600'}`}>
                                {account.browser_session_ready ? 'Browser 会话就绪' : 'Browser 会话未就绪'}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 ${account.automation_ready ? 'bg-violet-100 text-violet-800' : 'bg-amber-100 text-amber-800'}`}>
                                {account.automation_ready ? '可参与自动化' : '未完成独立接入'}
                              </span>
                            </div>
                            {account.last_login_message && (
                              <div className="text-xs text-muted-foreground">{account.last_login_message}</div>
                            )}
                            {healthCheck && (
                              <div className={`mt-2 rounded-md border px-3 py-2 text-xs ${
                                healthCheck.twikit_ok || healthCheck.browser_session_ready
                                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                                  : 'border-amber-200 bg-amber-50 text-amber-900'
                              }`}>
                                <div className="font-medium">
                                  最近检测：{new Date(healthCheck.checked_at).toLocaleString()}
                                </div>
                                <div className="mt-1">{healthCheck.twikit_message}</div>
                                <div className="mt-1">{healthCheck.browser_message}</div>
                              </div>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button type="button" variant="outline" size="sm" onClick={() => handleLoadMatrixAccount(account)}>
                              载入表单
                            </Button>
                            <Button type="button" variant="outline" size="sm" onClick={() => handleShowAccountGuide(account)}>
                              {showGuide ? '收起接入指引' : '查看接入指引'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => handleCheckMatrixAccountHealth(account)}
                              disabled={checkingAccountId === account.id}
                            >
                              {checkingAccountId === account.id ? '检测中' : '检测可用性'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => handleActivateMatrixAccount(account)}
                              disabled={account.is_active || activatingAccountId === account.id}
                            >
                              {activatingAccountId === account.id ? '切换中' : account.is_active ? '已激活' : '设为活跃'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteMatrixAccount(account)}
                              disabled={deletingAccountId === account.id}
                            >
                              {deletingAccountId === account.id ? '删除中' : '删除'}
                            </Button>
                          </div>
                        </div>
                        {showGuide && (
                          <div className="mt-3 rounded-md border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-900">
                            <div className="font-medium">账号 @{account.username} 的本地独立接入步骤</div>
                            <div className="mt-2">1. 在你电脑上打开一个全新的 Chrome Profile，只登录 @{account.username}，不要在这个 Profile 里再切别的 X 账号。</div>
                            <div className="mt-1">2. 确认这个 Profile 当前能正常访问 X 首页、搜索页和通知页，再从这个 Profile 导出 Cookie。</div>
                            <div className="mt-1">3. 在本页下方的 Cookie 管理器里，把 Cookie 明确绑定到 `{account.account_key}`，不要绑错到别的矩阵账号。</div>
                            <div className="mt-1">4. 导入后先点这张卡片里的“检测可用性”，确认 Twikit 身份和 Browser 会话状态都对上。</div>
                            <div className="mt-1">5. 只有当这个账号检测通过后，再去接入下一个账号。不要在同一个浏览器 Profile 里连续切号导 Cookie。</div>
                            <div className="mt-2 text-sky-800">
                              当前状态：
                              {account.cookie_ready ? ' 已有独立 Cookie；' : ' 还没有独立 Cookie；'}
                              {account.browser_session_ready ? ' 已有独立 Browser 会话。' : ' 还没有独立 Browser 会话。'}
                            </div>
                          </div>
                        )}
                      </div>
                    )})}
                  </div>
                )}
              </div>

              <div className="pt-4 border-t">
                <div className="mb-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
                  <div className="font-medium">外部浏览器辅助注册</div>
                  <div className="mt-1">
                    如果你不想用 noVNC 接管，就在你自己的浏览器完成注册/登录，然后回到这里导入 Cookie 并一键接入矩阵。
                  </div>
                  <div className="mt-2 text-xs text-sky-800">
                    推荐流程：1. 先填写用户名/邮箱 2. 保存待接入账号 3. 打开 X 注册页在外部浏览器完成注册或登录 4. 回来导入该账号 Cookie 5. 点击“注册完成后设为活跃”。
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button type="button" variant="outline" onClick={openExternalSignupPage}>
                      打开 X 注册页
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handlePrepareRegistrationAccount}
                      disabled={savingMatrixAccount || !twitterUsername}
                    >
                      {savingMatrixAccount ? '处理中' : '保存待接入账号'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCompleteRegistrationAccess}
                      disabled={savingMatrixAccount || !twitterUsername}
                    >
                      {savingMatrixAccount ? '处理中' : '注册完成后设为活跃'}
                    </Button>
                  </div>
                </div>

                <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
                  <div className="font-medium">Playwright 人工接管登录</div>
                  <div className="mt-1">
                    {browserTakeover?.manual_login_active
                      ? `人工接管浏览器已启动${browserTakeover.username ? `，当前账号 @${browserTakeover.username}` : ''}。请在远程浏览器里亲自完成账号密码登录。`
                      : '如果你要接手 Playwright 的账号密码登录，请先填写账号信息，然后启动人工接管浏览器。'}
                  </div>
                  <div className="mt-2 text-xs text-blue-800">
                    这不是学习你的操作行为，而是把 Playwright 浏览器直接交给你远程操作。登录成功后，再点“完成并保存会话”。
                  </div>
                  {browserTakeover?.vnc_url && (
                    <div className="mt-2 text-xs text-blue-800 break-all">
                      远程接管地址：{browserTakeover.vnc_url}
                    </div>
                  )}
                  {browserTakeover?.session_health && (
                    <div className={`mt-3 rounded-md border px-3 py-2 text-xs ${
                      browserTakeover.session_health.ok
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                        : 'border-amber-200 bg-amber-50 text-amber-900'
                    }`}>
                      <div className="font-medium">{browserTakeover.session_health.summary}</div>
                      <div className="mt-2 space-y-1">
                        {browserTakeover.session_health.checks.map((item) => (
                          <div key={item.name}>
                            {item.ok ? 'OK' : 'FAIL'} · {item.name} · {item.detail}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleStartBrowserTakeover}
                      disabled={startingBrowserTakeover || !twitterUsername}
                    >
                      {startingBrowserTakeover ? '启动中' : '启动人工接管'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => openBrowserTakeoverWindow(browserTakeover)}
                      disabled={!browserTakeover?.vnc_url}
                    >
                      打开接管窗口
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCompleteBrowserTakeover}
                      disabled={completingBrowserTakeover || !twitterUsername}
                    >
                      {completingBrowserTakeover ? '保存中' : '完成并保存会话'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCancelBrowserTakeover}
                      disabled={cancelingBrowserTakeover || !browserTakeover?.manual_login_active}
                    >
                      {cancelingBrowserTakeover ? '关闭中' : '关闭人工接管'}
                    </Button>
                  </div>
                </div>

                <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
                  <div className="font-medium">Browser 会话记忆</div>
                  <div className="mt-1">
                    {browserSession?.ready
                      ? `当前 Browser 会话已就绪${browserSession.username ? `，账号 @${browserSession.username}` : ''}${browserSession.updated_at ? `，最近同步 ${new Date(browserSession.updated_at).toLocaleString('zh-CN')}` : ''}。`
                      : '当前还没有可复用的 Browser 会话。你可以先导入 Cookie 或完成一次成功登录，然后点下方按钮同步。'}
                  </div>
                  <div className="mt-2 text-xs text-slate-600">
                    这一步会把当前合法认证状态保存为账号级 Browser 会话，后续 Playwright 优先复用，不再依赖重复密码登录。
                  </div>
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleSyncBrowserSession}
                      disabled={syncingBrowserSession}
                    >
                      {syncingBrowserSession ? '同步中' : '同步到 Browser 会话'}
                    </Button>
                  </div>
                </div>

                <label className="text-sm font-medium">Twitter 账号登录</label>
                <p className="text-xs text-muted-foreground mb-3">
                  仅在 Cookie 不可用时再尝试。若 Browser 模式提示 <code>399</code> 或 “Could not log you in now”，通常说明 X 拒绝当前密码登录环境，应回到 Cookie 方式。
                </p>
                {cookieStatus?.configured && (
                  <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                    当前活跃认证账号：
                    <span className="font-medium"> @{cookieStatus.username || cookieStatus.account_name}</span>
                    {cookieStatus.validation_mode && `，认证方式：${cookieStatus.validation_mode}`}
                  </div>
                )}
                {hasAccountMismatch && (
                  <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    检测到账号不一致：设置中的账号与当前 Cookie 生效账号不同。页面已优先按当前 Cookie 账号
                    <span className="font-medium"> @{activeCookieUsername}</span>
                    展示，请先清空旧 Cookie 或重新导入目标账号的 Cookie。
                  </div>
                )}
                <div className="grid gap-3">
                  <Input
                    value={twitterUsername}
                    onChange={(e) => setTwitterUsername(e.target.value)}
                    placeholder="用户名 (如 @username)"
                  />
                  <Input
                    value={twitterEmail}
                    onChange={(e) => setTwitterEmail(e.target.value)}
                    placeholder="注册邮箱"
                  />
                  <Input
                    type="password"
                    value={twitterPassword}
                    onChange={(e) => setTwitterPassword(e.target.value)}
                    placeholder={twitterPasswordSaved ? '密码已保存 (留空使用已保存密码)' : '密码'}
                  />
                </div>
                <div className="flex items-center gap-4 mt-3">
                  <Button
                    onClick={handleTwitterLogin}
                    disabled={loggingIn || !twitterUsername || !twitterEmail || (!twitterPassword && !twitterPasswordSaved)}
                  >
                    {loggingIn ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <LogIn className="h-4 w-4 mr-2" />
                    )}
                    登录 Twitter
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => handleSaveMatrixAccount(false)}
                    disabled={savingMatrixAccount || !twitterUsername}
                  >
                    {savingMatrixAccount ? '保存中' : '保存到矩阵'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => handleSaveMatrixAccount(true)}
                    disabled={savingMatrixAccount || !twitterUsername}
                  >
                    {savingMatrixAccount ? '处理中' : '保存并设为活跃'}
                  </Button>
                  {loginResult && (
                    <div className={`flex items-start gap-2 ${loginResult.success ? 'text-green-600' : 'text-red-600'}`}>
                      {loginResult.success ? <CheckCircle className="h-4 w-4 mt-0.5" /> : <XCircle className="h-4 w-4 mt-0.5" />}
                      <div className="text-sm">
                        <div>
                          {loginResult.message}
                          {loginResult.detail && ` (${loginResult.detail})`}
                        </div>
                        {!loginResult.success && (
                          <div className="text-xs opacity-80 mt-1">
                            Browser 登录失败时，优先改用 Cookie 导入；如果接口直接返回 502/500，请先检查 backend 日志与代理连通性。
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 pt-4 border-t">
              <Button onClick={testTwitterConnection} disabled={testingTwitter}>
                {testingTwitter ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                测试连接
              </Button>

              {twitterTest && (
                <div
                  className={`flex items-start gap-2 ${
                    twitterTest.success ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {twitterTest.success ? (
                    <CheckCircle className="h-4 w-4 mt-0.5" />
                  ) : (
                    <XCircle className="h-4 w-4 mt-0.5" />
                  )}
                  <div className="text-sm">
                    <div>
                      {twitterTest.message}
                      {twitterTest.detail && ` (${twitterTest.detail})`}
                    </div>
                    {!twitterTest.success && (
                      <div className="text-xs opacity-80 mt-1">
                        连接测试失败不一定是代码问题，也可能是 Cookie 过期、代理异常、X 返回风控页，或 Browser 执行层未就绪。
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>LLM配置</CardTitle>
            <CardDescription>配置OpenAI兼容的LLM服务</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4">
              <div>
                <label className="text-sm font-medium">API Base URL</label>
                <Input
                  value={settings.llm_api_base || ''}
                  onChange={(e) => setSettings({ ...settings, llm_api_base: e.target.value })}
                  onBlur={(e) => handleSave('llm_api_base', e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm font-medium">API Key</label>
                <Input
                  type="password"
                  value={settings.llm_api_key || ''}
                  onChange={(e) => setSettings({ ...settings, llm_api_key: e.target.value })}
                  onBlur={(e) => handleSave('llm_api_key', e.target.value)}
                  placeholder="sk-xxxxxxxxxxxxxxxx"
                  className="mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  API Key 会加密保存到数据库
                </p>
              </div>

              <div>
                <label className="text-sm font-medium">模型</label>
                <Input
                  value={settings.llm_model || ''}
                  onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
                  onBlur={(e) => handleSave('llm_model', e.target.value)}
                  placeholder="gpt-4o"
                  className="mt-1"
                />
              </div>
            </div>

            <div className="flex items-center gap-4 pt-4 border-t">
              <Button onClick={testLLMConnection} disabled={testingLLM}>
                {testingLLM ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                测试连接
              </Button>

              {llmTest && (
                <div
                  className={`flex items-center gap-2 ${
                    llmTest.success ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {llmTest.success ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  <span className="text-sm">
                    {llmTest.message}
                    {llmTest.detail && ` (${llmTest.detail})`}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>使用说明</CardTitle>
          </CardHeader>
          <CardContent className="prose prose-sm max-w-none">
            <div className="space-y-4 text-sm text-muted-foreground">
              <div>
                <h4 className="font-medium text-foreground">Twikit模式 (推荐)</h4>
                <p>
                  使用Twitter内部API，免费无限制。在上方 Twitter 配置区域直接输入账号信息并登录即可。
                </p>
                <p className="mt-2 text-yellow-600">注意：首次登录可能需要通过邮箱/手机验证</p>
              </div>

              <div>
                <h4 className="font-medium text-foreground">Twitter API模式 (付费)</h4>
                <p>
                  需要在 <code>.env</code> 文件中配置以下环境变量：
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>TWITTER_API_KEY</li>
                  <li>TWITTER_API_SECRET</li>
                  <li>TWITTER_ACCESS_TOKEN</li>
                  <li>TWITTER_ACCESS_TOKEN_SECRET</li>
                  <li>TWITTER_BEARER_TOKEN</li>
                </ul>
              </div>

              <div>
                <h4 className="font-medium text-foreground">Playwright模式</h4>
                <p>
                  需要在 <code>.env</code> 文件中配置：
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>TWITTER_USERNAME</li>
                  <li>TWITTER_PASSWORD</li>
                </ul>
              </div>

              <div>
                <h4 className="font-medium text-foreground">LLM服务</h4>
                <p>
                  在上方 LLM 配置区域直接输入 API Key、API Base URL 和模型名称即可。
                </p>
                <p className="mt-2">
                  支持的服务：
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Deepseek (推荐): https://api.deepseek.com, deepseek-chat</li>
                  <li>OpenAI: https://api.openai.com/v1, gpt-4o</li>
                  <li>其他 OpenAI 兼容服务</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
