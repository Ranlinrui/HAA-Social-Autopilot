import { useState } from 'react'
import { Eye, EyeOff, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

const API_BASE = '/api'

interface TestResult {
  is_valid: boolean
  message: string
  username?: string
}

export default function TwitterCookieManager() {
  const [authToken, setAuthToken] = useState('')
  const [ct0, setCt0] = useState('')
  const [accountName, setAccountName] = useState('')
  const [showTokens, setShowTokens] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const handleTest = async () => {
    if (!authToken || !ct0) {
      setTestResult({ is_valid: false, message: 'Please provide both auth_token and ct0' })
      return
    }

    setIsTesting(true)
    setTestResult(null)

    try {
      const response = await fetch(`${API_BASE}/cookies/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auth_token: authToken,
          ct0: ct0,
          account_name: accountName || 'default'
        })
      })

      const result = await response.json()
      setTestResult(result)

    } catch (error) {
      setTestResult({ is_valid: false, message: 'Network error. Please try again.' })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = async () => {
    if (!authToken || !ct0) {
      setSaveMessage({ type: 'error', text: 'Please provide both auth_token and ct0' })
      return
    }

    setIsSaving(true)
    setSaveMessage(null)

    try {
      const response = await fetch(`${API_BASE}/cookies/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auth_token: authToken,
          ct0: ct0,
          account_name: accountName || 'default'
        })
      })

      if (response.ok) {
        setSaveMessage({ type: 'success', text: 'Cookies saved successfully!' })
      } else {
        const error = await response.json()
        setSaveMessage({ type: 'error', text: error.detail || 'Failed to save cookies' })
      }

    } catch (error) {
      setSaveMessage({ type: 'error', text: 'Network error. Please try again.' })
    } finally {
      setIsSaving(false)
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
          <label htmlFor="account_name" className="text-sm font-medium">账号名称（可选）</label>
          <Input
            id="account_name"
            placeholder="例如: my_twitter_account"
            value={accountName}
            onChange={(e) => setAccountName(e.target.value)}
          />
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
