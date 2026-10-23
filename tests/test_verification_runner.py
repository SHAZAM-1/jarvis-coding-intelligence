"""Tests for the non-executing verification gate."""

import unittest
from src.verification_runner import (
    MAX_SOURCE_BYTES, VerificationInputError, verify_python_source,
)


class VerificationRunnerTests(unittest.TestCase):
    def test_valid_python_is_syntax_valid(self):
        result = verify_python_source("def add(a, b):\n    return a + b\n")
        self.assertEqual(result["status"], "syntax_valid")
        self.assertTrue(result["syntax_valid"])
        self.assertFalse(result["verified_fix"])
        self.assertIsNone(result["error"])

    def test_invalid_python_is_rejected(self):
        result = verify_python_source("def add(:\n    return 1\n")
        self.assertEqual(result["status"], "syntax_invalid")
        self.assertFalse(result["syntax_valid"])
        self.assertFalse(result["verified_fix"])
        self.assertEqual(result["error"]["type"], "SyntaxError")

    def test_code_is_not_claimed_as_verified(self):
        result = verify_python_source("print('hello')\n")
        self.assertFalse(result["verified_fix"])
        self.assertIn("unit_tests", result["checks_not_performed"])
        self.assertIn(
            "behavioral_correctness", result["checks_not_performed"]
        )

    def test_source_hash_is_recorded(self):
        self.assertEqual(len(verify_python_source("x = 1\n")["sha256"]), 64)

    def test_path_traversal_filename_is_rejected(self):
        with self.assertRaises(VerificationInputError):
            verify_python_source("x = 1", filename="../important.py")

    def test_non_python_filename_is_rejected(self):
        with self.assertRaises(VerificationInputError):
            verify_python_source("x = 1", filename="candidate.ps1")

    def test_non_string_source_is_rejected(self):
        with self.assertRaises(VerificationInputError):
            verify_python_source(None)

    def test_oversized_source_is_rejected(self):
        with self.assertRaises(VerificationInputError):
            verify_python_source(" " * (MAX_SOURCE_BYTES + 1))

    def test_syntax_error_includes_location(self):
        result = verify_python_source("if True print('bad')\n")
        self.assertEqual(result["status"], "syntax_invalid")
        self.assertIsNotNone(result["error"]["line"])

    def test_filename_must_be_a_simple_name(self):
        for filename in ("", ".", "..", "folder/candidate.py", "folder\\candidate.py"):
            with self.subTest(filename=filename):
                with self.assertRaises(VerificationInputError):
                    verify_python_source("x = 1", filename=filename)


if __name__ == "__main__":
    unittest.main()
