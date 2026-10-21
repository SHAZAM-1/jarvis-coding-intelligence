"""Tests for bounded, proposal-only self-correction."""

import unittest
from unittest.mock import Mock
from src.self_corrector import CorrectionLimitReached, SelfCorrector


class SelfCorrectorTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.generate.return_value = (
            "CAUSE: Incorrect attribute access.\n"
            "PROPOSED FIX: Validate the input type."
        )

    def test_generates_a_proposal(self):
        result = SelfCorrector(self.client).propose(
            task="Fix the parser",
            current_code="value = data.get('name')",
            failure_output="AttributeError: list has no attribute get",
        )
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(result["error_category"], "missing_attribute")
        self.assertFalse(result["verified"])
        self.assertFalse(result["applied"])
        self.client.generate.assert_called_once()

    def test_second_attempt_is_allowed(self):
        corrector = SelfCorrector(self.client, max_attempts=2)
        for _ in range(2):
            corrector.propose("Fix parser", "pass", "AssertionError: failed")
        self.assertEqual(corrector.attempts_used, 2)
        self.assertEqual(self.client.generate.call_count, 2)

    def test_third_attempt_is_rejected(self):
        corrector = SelfCorrector(self.client, max_attempts=2)
        for _ in range(2):
            corrector.propose("Fix parser", "pass", "AssertionError: failed")
        with self.assertRaises(CorrectionLimitReached):
            corrector.propose("Fix parser", "pass", "AssertionError: still failed")
        self.assertEqual(self.client.generate.call_count, 2)

    def test_invalid_attempt_limit_is_rejected(self):
        for value in (0, 3, -1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SelfCorrector(self.client, max_attempts=value)

    def test_empty_failure_is_rejected(self):
        with self.assertRaises(ValueError):
            SelfCorrector(self.client).propose("Fix code", "pass", "")
        self.client.generate.assert_not_called()

    def test_failed_model_call_still_consumes_attempt(self):
        self.client.generate.side_effect = RuntimeError("model unavailable")
        corrector = SelfCorrector(self.client, max_attempts=1)
        with self.assertRaises(RuntimeError):
            corrector.propose("Fix code", "pass", "AssertionError: failed")
        self.assertEqual(corrector.attempts_used, 1)
        with self.assertRaises(CorrectionLimitReached):
            corrector.propose("Fix code", "pass", "AssertionError: failed")
        self.assertEqual(self.client.generate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
