import unittest
from types import SimpleNamespace

from app.services.scheduler import should_skip_failed_retry


class SchedulerTests(unittest.TestCase):
    def test_should_skip_failed_retry_for_restricted_errors(self):
        self.assertTrue(
            should_skip_failed_retry(
                SimpleNamespace(error_message="Authorization: This request looks like it might be automated. [226]")
            )
        )
        self.assertTrue(
            should_skip_failed_retry(
                SimpleNamespace(error_message="Authorization: Denied by access control: Missing TwitterUserNotSuspended [37]")
            )
        )
        self.assertFalse(
            should_skip_failed_retry(
                SimpleNamespace(error_message="temporary network timeout")
            )
        )


if __name__ == "__main__":
    unittest.main()
