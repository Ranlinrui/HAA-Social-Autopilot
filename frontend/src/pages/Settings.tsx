import { useEffect, useState } from 'react'
import { RefreshCw, CheckCircle, XCircle, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { settingsApi } from '@/services/api'
import TwitterCookieManager from '@/components/TwitterCookieManager'

interface TestResult {
  success: boolean
  message: string
  detail?: string
}

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

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const res = await settingsApi.get()
      setSettings(res.settings)
      if (res.settings.twitter_username) setTwitterUsername(res.settings.twitter_username)
      if (res.settings.twitter_email) setTwitterEmail(res.settings.twitter_email)
      if (res.settings.twitter_password_saved) setTwitterPasswordSaved(true)
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (key: string, value: string) => {
    setSaving(true)
    try {
      await settingsApi.update(key, value)
      setSettings({ ...settings, [key]: value })
    } catch (error) {
      console.error('Failed to save setting:', error)
    } finally {
      setSaving(false)
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
      }
    } catch (error) {
      setLoginResult({ success: false, message: '登录请求失败' })
    } finally {
      setLoggingIn(false)
    }
  }

  const testTwitterConnection = async () => {
    setTestingTwitter(true)
    setTwitterTest(null)
    try {
      const res = await settingsApi.testTwitter()
      setTwitterTest({
        success: res.success,
        message: res.message,
        detail: res.username ? `@${res.username}` : undefined,
      })
    } catch (error) {
      setTwitterTest({
        success: false,
        message: '连接失败',
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
        message: '连接失败',
      })
    } finally {
      setTestingLLM(false)
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

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Twitter配置</CardTitle>
            <CardDescription>
              配置 Twitter 执行模式与账号登录信息
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

              <div className="pt-4 border-t">
                <label className="text-sm font-medium">Twitter 账号登录</label>
                <p className="text-xs text-muted-foreground mb-3">
                  输入账号信息登录，登录成功后凭证会自动保存
                </p>
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
                    <div className={`flex items-center gap-2 ${loginResult.success ? 'text-green-600' : 'text-red-600'}`}>
                      {loginResult.success ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                      <span className="text-sm">
                        {loginResult.message}
                        {loginResult.detail && ` (${loginResult.detail})`}
                      </span>
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
                  className={`flex items-center gap-2 ${
                    twitterTest.success ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {twitterTest.success ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : (
                    <XCircle className="h-4 w-4" />
                  )}
                  <span className="text-sm">
                    {twitterTest.message}
                    {twitterTest.detail && ` (${twitterTest.detail})`}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Twitter Cookie Manager */}
        <TwitterCookieManager />

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
