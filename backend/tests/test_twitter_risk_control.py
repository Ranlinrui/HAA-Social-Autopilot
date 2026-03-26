import unittest

from app.services.twitter_risk_control import TwitterRiskControl


class TwitterRiskControlTests(unittest.TestCase):
    def test_automation_failure_enters_read_only_and_recovery(self):
        control = TwitterRiskControl()

        control.record_failure("publish", "Authorization: This request looks like it might be automated. [226]", account_key="user_a")
        state = control.get_state("user_a")

        self.assertEqual(state["risk_stage"], "read_only")
        self.assertTrue(state["write_blocked"])
        self.assertIsNotNone(state["read_only_until"])
        self.assertIsNotNone(state["recovery_until"])

    def test_auth_failure_enters_auth_cooldown(self):
        control = TwitterRiskControl()

        control.record_failure("reply", 'status: 401, message: {"errors":[{"message":"Could not authenticate you","code":32}]}', account_key="user_a")
        state = control.get_state("user_a")

        self.assertEqual(state["risk_stage"], "auth_cooldown")
        self.assertTrue(state["write_blocked"])

    def test_budget_limit_blocks_when_exceeded(self):
        control = TwitterRiskControl()

        for _ in range(6):
            control.assert_action_allowed("publish", account_key="user_a")
            control.record_success("publish", account_key="user_a")

        with self.assertRaisesRegex(RuntimeError, "配额上限"):
            control.assert_action_allowed("publish", account_key="user_a")

    def test_account_states_are_isolated(self):
        control = TwitterRiskControl()

        control.record_failure("publish", "Authorization: This request looks like it might be automated. [226]", account_key="user_a")

        self.assertEqual(control.get_state("user_a")["risk_stage"], "read_only")
        self.assertEqual(control.get_state("user_b")["risk_stage"], "normal")
        self.assertFalse(control.get_state("user_b")["is_persisted"])

    def test_list_states_returns_multiple_accounts(self):
        control = TwitterRiskControl()

        control.record_failure("publish", "Authorization: This request looks like it might be automated. [226]", account_key="user_a")
        control.record_failure("reply", 'status: 401, message: {"errors":[{"message":"Could not authenticate you","code":32}]}', account_key="user_b")

        rows = control.list_states()
        keys = {row["risk_account_key"] for row in rows}

        self.assertIn("user_a", keys)
        self.assertIn("user_b", keys)

    def test_get_state_does_not_persist_account_on_read(self):
        control = TwitterRiskControl()

        state = control.get_state("user_x")

        self.assertEqual(state["risk_stage"], "normal")
        self.assertFalse(state["is_persisted"])
        self.assertEqual(control.list_states(), [])

    def test_reset_account_removes_only_target_account(self):
        control = TwitterRiskControl()

        control.record_failure("publish", "Authorization: This request looks like it might be automated. [226]", account_key="user_a")
        control.record_failure("reply", 'status: 401, message: {"errors":[{"message":"Could not authenticate you","code":32}]}', account_key="user_b")

        removed = control.reset_account("user_a")

        self.assertTrue(removed)
        self.assertEqual(control.get_state("user_a")["risk_stage"], "normal")
        self.assertEqual(control.get_state("user_b")["risk_stage"], "auth_cooldown")
        self.assertFalse(control.get_state("user_a")["is_persisted"])
        self.assertTrue(control.get_state("user_b")["is_persisted"])


if __name__ == "__main__":
    unittest.main()
