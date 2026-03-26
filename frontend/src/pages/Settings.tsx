import { useEffect, useState } from 'react'
import { RefreshCw, CheckCircle, XCircle, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { formatTwitterActionError, settingsApi } from '@/services/api'
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
  const [resettingRiskAccount, setResettingRiskAccount] = useState<string | null>(null)
  const [pageMessage, setPageMessage] = useState<PageMessage | null>(null)

  const activeCookieUsername = cookieStatus?.username || cookieStatus?.account_name || ''
  const hasAccountMismatch = Boolean(
    activeCookieUsername &&
    twitterUsername &&
    activeCookieUsername !== twitterUsername
  )

  useEffect(() => {
    loadSettings()
  }, [])

  const refreshAuthState = async () => {
    const [next, accounts] = await Promise.allSettled([
      settingsApi.getTwitterAuthState(),
      settingsApi.getTwitterRiskAccounts(),
    ])

    const nextAuthState = next.status === 'fulfilled' ? next.value : null
    const nextRiskAccounts = accounts.status === 'fulfilled' ? accounts.value : []

    setAuthState(nextAuthState)
    setRiskAccounts(nextRiskAccounts)

    if (next.status === 'rejected' || accounts.status === 'rejected') {
      const firstError = next.status === 'rejected'
        ? next.reason
        : accounts.status === 'rejected'
          ? accounts.reason
          : null
      setPageMessage({
        tone: 'error',
        title: '认证状态刷新失败',
        message: formatTwitterActionError(firstError, '部分认证状态加载失败'),
      })
    }

    return nextAuthState
  }

  const loadSettings = async () => {
    let hasFailure = false

    try {
      setPageMessage(null)
      const [res, authState, accounts] = await Promise.allSettled([
        settingsApi.get(),
        settingsApi.getTwitterAuthState(),
        settingsApi.getTwitterRiskAccounts(),
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
                : null
        setPageMessage({
          tone: 'error',
          title: '设置页部分数据加载失败',
          message: formatTwitterActionError(firstError, '部分设置数据加载失败'),
        })
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
      setPageMessage({
        tone: 'error',
        title: '设置页加载失败',
        message: formatTwitterActionError(error, '设置数据加载失败'),
      })
    } finally {
      setLoading(false)
    }
  }

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
      console.error('Failed to save setting:', error)
      setPageMessage({
        tone: 'error',
        title: '保存设置失败',
        message: formatTwitterActionError(error, '保存设置失败'),
      })
    } finally {
      setSaving(false)
    }
  }

  const handleCookieStatusChange = (status: CookieStatus | null) => {
    setCookieStatus(status)
    if (!status?.configured) {
      refreshAuthState()
      setTwitterUsername('')
      setSettings((current) => ({ ...current, twitter_username: '' }))
      setLoginResult(null)
      setTwitterTest(null)
      return
    }
    refreshAuthState()
    if (status.username || status.account_name) {
      const activeUsername = status.username || status.account_name || ''
      setTwitterUsername(activeUsername)
      setSettings((current) => ({ ...current, twitter_username: activeUsername }))
    }
  }

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
        await refreshAuthState()
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
      await refreshAuthState()
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
      console.error('Failed to reset risk account:', error)
      setPageMessage({
        tone: 'error',
        title: '重置风控失败',
        message: formatTwitterActionError(error, '重置风控失败'),
      })
    } finally {
      setResettingRiskAccount(null)
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

              <div className="pt-2">
                <TwitterCookieManager onStatusChange={handleCookieStatusChange} />
              </div>

              <TwitterRiskBanner state={authState} />

              <TwitterRiskAccountPanel
                items={riskAccounts}
                activeUsername={authState?.active_username}
                resettingKey={resettingRiskAccount}
                onReset={handleResetRiskAccount}
              />

              <div className="pt-4 border-t">
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
