"""Tests for deterministic error classification."""

import unittest
from src.error_analyzer import analyze_error


class ErrorAnalyzerTests(unittest.TestCase):
    def test_module_not_found(self):
        self.assertEqual(
            analyze_error("ModuleNotFoundError: missing")["category"],
            "missing_import",
        )

    def test_syntax_error(self):
        self.assertEqual(
            analyze_error("SyntaxError: invalid syntax")["category"],
            "syntax_error",
        )

    def test_attribute_error(self):
        self.assertEqual(
            analyze_error("AttributeError: missing")["category"],
            "missing_attribute",
        )

    def test_assertion_failure(self):
        self.assertEqual(
            analyze_error("AssertionError: expected 4, got 5")["category"],
            "assertion_failure",
        )

    def test_unknown_error_is_not_guessed(self):
        result = analyze_error("An unfamiliar failure occurred")
        self.assertEqual(result["category"], "unknown")
        self.assertTrue(result["needs_investigation"])

    def test_empty_error(self):
        result = analyze_error("  ")
        self.assertEqual(result["category"], "unknown")
        self.assertTrue(result["needs_investigation"])

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(TypeError):
            analyze_error(None)

    def test_evidence_is_bounded(self):
        self.assertLessEqual(
            len(analyze_error("X" * 10000)["evidence"]), 4000
        )


if __name__ == "__main__":
    unittest.main()
