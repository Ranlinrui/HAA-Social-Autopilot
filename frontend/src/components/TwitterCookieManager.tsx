import { useCallback, useEffect, useRef, useState } from 'react'
import { Eye, EyeOff, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { formatTwitterActionError } from '@/services/api'

const API_BASE = '/api'

interface TestResult {
  is_valid: boolean
  message: string
  username?: string
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

interface TwitterCookieManagerProps {
  onStatusChange?: (status: CookieStatus | null) => void
  defaultAccountName?: string
  accountOptions?: Array<{ account_key: string; username: string }>
}

function formatFetchErrorMessage(error: unknown, fallback: string) {
  return formatTwitterActionError(
    typeof error === 'object' && error !== null && 'response' in error
      ? error
      : { message: error instanceof Error ? error.message : String(error || '') },
    fallback,
  )
}

async function requestJson(path: string, init?: RequestInit) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), 30000)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw { response: { status: response.status, data: payload } }
    }
    return payload
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw { message: 'timeout of 30000ms exceeded' }
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export default function TwitterCookieManager({ onStatusChange, defaultAccountName, accountOptions = [] }: TwitterCookieManagerProps) {
  const [authToken, setAuthToken] = useState('')
  const [ct0, setCt0] = useState('')
  const [accountName, setAccountName] = useState('')
  const [showTokens, setShowTokens] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [statusLoading, setStatusLoading] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [cookieStatus, setCookieStatus] = useState<CookieStatus | null>(null)
  const onStatusChangeRef = useRef(onStatusChange)
  const statusRequestRef = useRef<Promise<void> | null>(null)

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange
  }, [onStatusChange])

  const loadStatus = useCallback(async () => {
    if (statusRequestRef.current) {
      await statusRequestRef.current
      return
    }

    const task = (async () => {
      setStatusLoading(true)
      try {
        const result = await requestJson('/cookies/status')
        setCookieStatus(result)
        onStatusChangeRef.current?.(result)
      } catch (error) {
        const fallback = { configured: false, message: formatFetchErrorMessage(error, '无法读取当前 Cookie 状态') }
        setCookieStatus(fallback)
        onStatusChangeRef.current?.(fallback)
      } finally {
        setStatusLoading(false)
      }
    })()

    statusRequestRef.current = task
    try {
      await task
    } finally {
      statusRequestRef.current = null
    }
  }, [])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  useEffect(() => {
    if (!accountName.trim() && defaultAccountName?.trim()) {
      setAccountName(defaultAccountName.trim().replace(/^@/, ''))
    }
  }, [accountName, defaultAccountName])

  const handleTest = async () => {
    if (!authToken || !ct0) {
      setTestResult({ is_valid: false, message: '请同时提供 auth_token 和 ct0' })
      return
    }

    setIsTesting(true)
    setTestResult(null)

    try {
      const result = await requestJson('/cookies/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auth_token: authToken,
          ct0: ct0,
          account_name: accountName.trim() || defaultAccountName?.trim().replace(/^@/, '') || 'default'
        })
      })
      setTestResult(result)
      await loadStatus()

    } catch (error) {
      setTestResult({ is_valid: false, message: formatFetchErrorMessage(error, 'Cookie 测试请求失败，请稍后重试。') })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = async () => {
    if (!authToken || !ct0) {
      setSaveMessage({ type: 'error', text: '请同时提供 auth_token 和 ct0' })
      return
    }

    setIsSaving(true)
    setSaveMessage(null)

    try {
      await requestJson('/cookies/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auth_token: authToken,
          ct0: ct0,
          account_name: accountName.trim() || defaultAccountName?.trim().replace(/^@/, '') || 'default'
        })
      })
      setSaveMessage({ type: 'success', text: 'Cookies 已保存。' })
      await loadStatus()

    } catch (error) {
      setSaveMessage({ type: 'error', text: formatFetchErrorMessage(error, '保存 Cookies 请求失败，请稍后重试。') })
    } finally {
      setIsSaving(false)
    }
  }

  const handleClear = async () => {
    setIsClearing(true)
    setSaveMessage(null)
    setTestResult(null)
    try {
      const result = await requestJson('/cookies/clear', {
        method: 'DELETE',
      })
      setAuthToken('')
      setCt0('')
      setAccountName('')
      setSaveMessage({ type: 'success', text: result.message || 'Cookies 已清空' })
    } catch (error) {
      setSaveMessage({ type: 'error', text: formatFetchErrorMessage(error, '清空 Cookies 请求失败，请稍后重试。') })
    } finally {
      await loadStatus()
      setIsClearing(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
          </svg>
          Twitter Cookie 管理
        </CardTitle>
        <CardDescription>
          使用 Cookies 方式登录 Twitter（推荐，避免频繁密码登录）
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-medium text-slate-900">当前 Cookie 状态</div>
              {statusLoading ? (
                <div className="text-slate-600 mt-1">读取中...</div>
              ) : cookieStatus?.configured ? (
                <div className="text-slate-700 mt-1">
                  已配置
                  {cookieStatus.account_name && `，账号标识: @${cookieStatus.account_name}`}
                  {cookieStatus.is_valid === false && '，当前标记为无效'}
                  {cookieStatus.is_expired && '，当前已过期'}
                </div>
              ) : (
                <div className="text-slate-600 mt-1">
                  {cookieStatus?.message || '当前未配置 Cookie'}
                </div>
              )}
            </div>
            <Button type="button" variant="outline" size="sm" onClick={loadStatus} disabled={statusLoading}>
              {statusLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : '刷新状态'}
            </Button>
          </div>
        </div>

        {/* Status Messages */}
        {saveMessage && (
          <div className={`p-3 rounded-lg flex items-center gap-2 ${
            saveMessage.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            {saveMessage.type === 'success' ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            <span>{saveMessage.text}</span>
          </div>
        )}

        {testResult && (
          <div className={`p-3 rounded-lg flex items-center gap-2 ${
            testResult.is_valid ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            {testResult.is_valid ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            <div>
              <div>{testResult.message}</div>
              {testResult.username && (
                <div className="text-sm">登录为: @{testResult.username}</div>
              )}
            </div>
          </div>
        )}

        {/* Account Name */}
        <div className="space-y-2">
          <label htmlFor="account_name" className="text-sm font-medium">绑定矩阵账号</label>
          {accountOptions.length > 0 ? (
            <select
              id="account_name"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
            >
              <option value="">选择一个矩阵账号</option>
              {accountOptions.map((item) => (
                <option key={item.account_key} value={item.account_key}>
                  @{item.username} ({item.account_key})
                </option>
              ))}
            </select>
          ) : (
            <Input
              id="account_name"
              placeholder="例如: my_twitter_account"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
            />
          )}
          <p className="text-xs text-muted-foreground">
            这份 Cookie 会绑定到指定矩阵账号，避免不同账号共用同一份会话。
          </p>
        </div>

        {/* Auth Token */}
        <div className="space-y-2">
          <label htmlFor="auth_token" className="text-sm font-medium">
            auth_token <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Input
              id="auth_token"
              type={showTokens ? 'text' : 'password'}
              placeholder="粘贴你的 auth_token"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
            >
              {showTokens ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* CT0 Token */}
        <div className="space-y-2">
          <label htmlFor="ct0" className="text-sm font-medium">
            ct0 (CSRF Token) <span className="text-red-500">*</span>
          </label>
          <Input
            id="ct0"
            type={showTokens ? 'text' : 'password'}
            placeholder="粘贴你的 ct0 token"
            value={ct0}
            onChange={(e) => setCt0(e.target.value)}
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={handleSave}
            disabled={isSaving || !authToken || !ct0}
            className="flex-1"
          >
            {isSaving ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              '保存 Cookies'
            )}
          </Button>

          <Button
            onClick={handleTest}
            disabled={isTesting || !authToken || !ct0}
            variant="outline"
            className="flex-1"
          >
            {isTesting ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                测试中...
              </>
            ) : (
              '测试 Cookies'
            )}
          </Button>

          <Button
            onClick={handleClear}
            disabled={isClearing}
            variant="outline"
            className="flex-1"
          >
            {isClearing ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                清理中...
              </>
            ) : (
              '清空 Cookies'
            )}
          </Button>
        </div>

        {/* Help Info */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-2">
          <div className="font-medium text-blue-900">如何获取 Cookies？</div>
          <ol className="list-decimal list-inside space-y-1 text-blue-800">
            <li>访问 x.com 并登录你的账号</li>
            <li>按 F12 打开开发者工具</li>
            <li>切换到 Application 标签</li>
            <li>左侧选择 Cookies → https://x.com</li>
            <li>找到并复制 auth_token 和 ct0 的值</li>
            <li>粘贴到上面的表单中</li>
          </ol>
        </div>

        {/* Important Notes */}
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm space-y-2">
          <div className="font-medium text-yellow-900">重要提示：</div>
          <ul className="list-disc list-inside space-y-1 text-yellow-800">
            <li>Cookies 通常有效期为 7-30 天</li>
            <li>如果 Cookies 10 分钟内失效，建议使用用户名/密码登录</li>
            <li>不要与他人分享你的 Cookies</li>
            <li>出现认证错误时及时更新 Cookies</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}
