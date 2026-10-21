"""Tests for deterministic task routing."""

import unittest

from src.task_router import choose_profile


class TaskRouterTests(unittest.TestCase):
    def test_simple_explanation_uses_fast_profile(self):
        self.assertEqual(
            choose_profile("Explain this line: x = x + 1"),
            "fast",
        )

    def test_ordinary_request_uses_balanced_profile(self):
        self.assertEqual(choose_profile("Help me write a Python parser"), "balanced")

    def test_complex_debugging_can_use_deep_profile(self):
        task = (
            "Find the root cause of this concurrency regression and memory leak; "
            "review this diff and failing tests."
        )
        self.assertEqual(choose_profile(task, "Traceback: failure", 3072), "deep")

    def test_deep_profile_is_reduced_when_memory_is_tight(self):
        task = (
            "Find the root cause of this concurrency regression and memory leak; "
            "review this diff and failing tests."
        )
        self.assertEqual(choose_profile(task, "Traceback: failure", 1900), "balanced")

    def test_unknown_memory_does_not_grant_deep_profile(self):
        task = (
            "Find the root cause of this concurrency regression and memory leak; "
            "review this diff and failing tests."
        )
        self.assertEqual(choose_profile(task, "Traceback: failure"), "balanced")


if __name__ == "__main__":
    unittest.main(verbosity=2)
