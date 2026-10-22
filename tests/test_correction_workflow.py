"""Tests for proposal -> syntax gate -> conservative learning records."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.correction_workflow import CorrectionWorkflow, extract_python_candidate
from src.learning_ledger import LearningLedger


class CorrectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.ledger_path = Path(self.temp_dir.name) / "learning.jsonl"
        self.ledger = LearningLedger(self.ledger_path)
        self.corrector = Mock()
        self.corrector.propose.return_value = {
            "attempt": 1,
            "error_category": "assertion_failure",
            "proposal": (
                "CAUSE: incorrect boundary.\n"
                "PROPOSED FIX:\n"
                "```python\n"
                "def add(a, b):\n    return a + b\n"
                "```\n"
                "VERIFICATION REQUIRED: run trusted tests."
            ),
            "verified": False,
            "applied": False,
        }
        self.workflow = CorrectionWorkflow(self.corrector, self.ledger)

    def test_extracts_exactly_one_python_candidate(self):
        candidate = extract_python_candidate(
            "Fix:\n```python\nx = 1\n```"
        )
        self.assertEqual(candidate, "x = 1\n")

    def test_rejects_missing_or_ambiguous_code_blocks(self):
        self.assertIsNone(extract_python_candidate("No source provided."))
        self.assertIsNone(
            extract_python_candidate(
                "```python\nx = 1\n```\n```python\ny = 2\n```"
            )
        )
        self.assertIsNone(extract_python_candidate("```python\n   \n```"))

    def test_syntax_valid_candidate_is_recorded_without_overclaiming(self):
        result = self.workflow.run(
            task="Fix add",
            current_code="def add(a, b):\n    return a - b\n",
            failure_output="AssertionError: expected 3",
        )
        self.assertEqual(result["status"], "syntax_valid")
        self.assertEqual(result["ledger_record"]["status"], "SYNTAX_VALID")
        self.assertFalse(result["applied"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["behaviorally_verified"])
        self.assertEqual(len(result["verification"]["sha256"]), 64)
        self.corrector.propose.assert_called_once()
        saved = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.assertNotIn("source", saved)
        self.assertNotIn("failure_output", saved)
        self.assertNotIn("return a + b", self.ledger_path.read_text(encoding="utf-8"))

    def test_syntax_invalid_candidate_is_not_promoted(self):
        self.corrector.propose.return_value["proposal"] = (
            "```python\ndef add(:\n    return 1\n```"
        )
        result = self.workflow.run("Fix add", "pass", "SyntaxError: invalid")
        self.assertEqual(result["status"], "syntax_invalid")
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")
        self.assertFalse(result["behaviorally_verified"])

    def test_missing_candidate_is_recorded_as_unverified(self):
        self.corrector.propose.return_value["proposal"] = "No code block."
        result = self.workflow.run("Fix add", "pass", "AssertionError: failed")
        self.assertEqual(result["status"], "candidate_missing_or_ambiguous")
        self.assertIsNone(result["candidate_source"])
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")
        self.assertIsNone(result["verification"])

    def test_workflow_does_not_execute_candidate_code(self):
        self.corrector.propose.return_value["proposal"] = (
            "```python\nraise RuntimeError('must not run')\n```"
        )
        result = self.workflow.run("Inspect candidate", "pass", "test failed")
        self.assertTrue(result["verification"]["syntax_valid"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["behaviorally_verified"])

    def test_requires_corrector_and_ledger_interfaces(self):
        with self.assertRaises(TypeError):
            CorrectionWorkflow(object(), self.ledger)
        with self.assertRaises(TypeError):
            CorrectionWorkflow(self.corrector, object())


if __name__ == "__main__":
    unittest.main(verbosity=2)
