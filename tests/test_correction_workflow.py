"""Tests for proposal -> syntax gate -> conservative learning records."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.behavioral_verifier import (
    BehavioralVerificationError,
    VerificationUnavailableError,
)
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

    def test_behavioral_execution_requires_configured_verifier(self):
        with self.assertRaisesRegex(
            VerificationUnavailableError, "No behavioral verifier is configured"
        ):
            self.workflow.verify_behavior(
                "def add(a, b):\n    return a + b\n",
                "add",
                [{"args": [1, 2], "kwargs": {}, "expected": 3}],
                allow_execution=True,
            )

    def test_behavioral_execution_requires_explicit_opt_in(self):
        verifier = Mock()
        workflow = CorrectionWorkflow(self.corrector, self.ledger, verifier)
        with self.assertRaisesRegex(
            VerificationUnavailableError, "explicitly opt in"
        ):
            workflow.verify_behavior(
                "def add(a, b):\n    return a + b\n",
                "add",
                [{"args": [1, 2], "kwargs": {}, "expected": 3}],
            )
        verifier.verify.assert_not_called()

    def test_normal_run_never_invokes_behavioral_verifier(self):
        verifier = Mock()
        workflow = CorrectionWorkflow(self.corrector, self.ledger, verifier)
        result = workflow.run("Fix add", "def add(a, b): return a-b", "AssertionError")
        self.assertEqual(result["status"], "syntax_valid")
        verifier.verify.assert_not_called()

    def test_successful_behavioral_result_uses_receipt_gated_ledger_api(self):
        source = "def add(a, b):\n    return a + b\n"
        receipt = SimpleNamespace(
            source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            success=True,
            case_count=2,
            passed_count=2,
            failed_count=0,
        )
        verifier = Mock()
        verifier.verify.return_value = SimpleNamespace(
            status="verified", receipt=receipt, failed_case_indices=()
        )
        self.ledger.append_verified_record = Mock(
            return_value={"status": "VERIFIED"}
        )
        workflow = CorrectionWorkflow(self.corrector, self.ledger, verifier)
        result = workflow.verify_behavior(
            source,
            "add",
            [{"args": [1, 2], "kwargs": {}, "expected": 3},
             {"args": [2, 3], "kwargs": {}, "expected": 5}],
            allow_execution=True,
            category="assertion_failure",
        )
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["behaviorally_verified"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["executed"])
        self.ledger.append_verified_record.assert_called_once_with(
            source=source,
            category="assertion_failure",
            summary=(
                "All 2 declared behavioral cases passed in the configured "
                "Docker sandbox."
            ),
            receipt=receipt,
        )

    def test_failed_behavioral_result_is_never_promoted(self):
        source = "def add(a, b):\n    return a - b\n"
        receipt = SimpleNamespace(
            source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            success=False,
            case_count=2,
            passed_count=1,
            failed_count=1,
        )
        verifier = Mock()
        verifier.verify.return_value = SimpleNamespace(
            status="behavioral_failed", receipt=receipt, failed_case_indices=(1,)
        )
        workflow = CorrectionWorkflow(self.corrector, self.ledger, verifier)
        result = workflow.verify_behavior(
            source,
            "add",
            [{"args": [1, 2], "kwargs": {}, "expected": 3},
             {"args": [2, 3], "kwargs": {}, "expected": 5}],
            allow_execution=True,
            category="assertion_failure",
        )
        self.assertEqual(result["status"], "behavioral_failed")
        self.assertFalse(result["behaviorally_verified"])
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")
        self.assertNotIn("verification", result["ledger_record"])

    def test_mismatched_behavioral_receipt_is_rejected_even_on_failure(self):
        source = "def add(a, b):\n    return a - b\n"
        receipt = SimpleNamespace(
            source_sha256=hashlib.sha256(b"different source").hexdigest(),
            success=False,
            case_count=1,
            passed_count=0,
            failed_count=1,
        )
        verifier = Mock()
        verifier.verify.return_value = SimpleNamespace(
            status="behavioral_failed", receipt=receipt, failed_case_indices=(0,)
        )
        workflow = CorrectionWorkflow(self.corrector, self.ledger, verifier)
        with self.assertRaisesRegex(BehavioralVerificationError, "does not match"):
            workflow.verify_behavior(
                source,
                "add",
                [{"args": [1, 2], "kwargs": {}, "expected": 3}],
                allow_execution=True,
                category="assertion_failure",
            )

    def test_requires_corrector_and_ledger_interfaces(self):
        with self.assertRaises(TypeError):
            CorrectionWorkflow(object(), self.ledger)
        with self.assertRaises(TypeError):
            CorrectionWorkflow(self.corrector, object())


if __name__ == "__main__":
    unittest.main(verbosity=2)
