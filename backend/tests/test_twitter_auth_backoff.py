import unittest

from app.services.twitter_auth_backoff import is_automation_failure


class TwitterAuthBackoffTests(unittest.TestCase):
    def test_is_automation_failure_matches_browser_account_restriction_markers(self):
        self.assertTrue(
            is_automation_failure(
                "Browser 账号状态受限：当前首页显示 Your account is suspended，账号暂时不可用于搜索、发帖、回复和引用。"
            )
        )
        self.assertTrue(
            is_automation_failure("Browser 搜索页加载失败：X 返回 Something went wrong. Try reloading.")
        )
        self.assertTrue(
            is_automation_failure("Browser 模式访问 X 页面失败，当前会话被返回为 JavaScript 错误页，请重新登录或更换浏览器环境")
        )


if __name__ == "__main__":
    unittest.main()
