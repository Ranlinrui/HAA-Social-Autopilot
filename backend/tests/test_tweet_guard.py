import unittest

from app.services.tweet_guard import is_publish_restricted_error


class TweetGuardTests(unittest.TestCase):
    def test_is_publish_restricted_error_matches_automation_and_account_limits(self):
        self.assertTrue(is_publish_restricted_error("Authorization: This request looks like it might be automated. [226]"))
        self.assertTrue(is_publish_restricted_error("Authorization: Denied by access control: Missing TwitterUserNotSuspended [37]"))
        self.assertFalse(is_publish_restricted_error("temporary proxy timeout"))


if __name__ == "__main__":
    unittest.main()
