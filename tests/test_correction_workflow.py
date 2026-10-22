"""Tests for the correction-to-verification workflow."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.docker_verifier import DockerFunctionVerifier
from src.correction_workflow import (
    CorrectionWorkflow, ProposalExtractionError, extract_candidate_source,
)
from src.learning_ledger import LearningLedger

SOURCE = "def add(a, b):\n    return a + b\n"
PROPOSAL = (
    "CAUSE:\nThe addition function is required.\n"
    "EVIDENCE:\nThe task requests addition.\n"
    "PROPOSED FIX:\n"
    "```python\n" + SOURCE + "```\n"
    "REGRESSION TESTS:\nCheck positive and negative operands.\n"
    "VERIFICATION REQUIRED:\nRun behavioral tests.\n"
    "UNCERTAINTIES:\nNone stated.\n"
)


class CorrectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.ledger_path = Path(self.temp_dir.name) / "learning.jsonl"
        self.ledger = LearningLedger(self.ledger_path)
        self.corrector = Mock()
        self.corrector.propose.return_value = {
            "proposal": PROPOSAL, "error_category": "assertion_failure",
            "attempt": 1, "verified": False, "applied": False,
        }

    def test_extractor_requires_one_python_block_in_fix_section(self):
        self.assertEqual(extract_candidate_source(PROPOSAL), SOURCE)

    def test_extractor_rejects_missing_fix_section(self):
        with self.assertRaises(ProposalExtractionError):
            extract_candidate_source("No structured proposal.")

    def test_extractor_rejects_multiple_code_blocks(self):
        proposal = PROPOSAL.replace(
            SOURCE + "```",
            SOURCE + "```\n```python\nx = 1\n```",
        )
        with self.assertRaises(ProposalExtractionError):
            extract_candidate_source(proposal)

    def test_syntax_only_never_claims_verified(self):
        result = CorrectionWorkflow(self.corrector, self.ledger).run(
            "Implement add", "def add(a, b): return a-b", "AssertionError: expected sum"
        )
        self.assertEqual(result["status"], "syntax_valid")
        self.assertFalse(result["verified"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["ledger_record"]["status"], "SYNTAX_VALID")
        self.assertEqual(self.ledger_path.read_text(encoding="utf-8").count("\n"), 1)

    def test_syntax_invalid_candidate_is_recorded_unverified(self):
        self.corrector.propose.return_value["proposal"] = PROPOSAL.replace(
            SOURCE, "def add(:\n    return 1\n"
        )
        result = CorrectionWorkflow(self.corrector, self.ledger).run(
            "Implement add", "pass", "SyntaxError: invalid syntax"
        )
        self.assertEqual(result["status"], "syntax_invalid")
        self.assertFalse(result["verified"])
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")

    def test_successful_trusted_verifier_creates_verified_record(self):
        digest = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        verifier = Mock(return_value={
            "status": "passed", "source_sha256": digest,
            "verifier_id": "isolated-test-adapter", "run_id": "run-0001",
            "checks_performed": ["behavioral_tests"],
            "commands": ["python -m unittest test_candidate"],
            "exit_code": 0, "test_count": 3,
            "timestamp": "2026-10-22T00:00:00Z",
        })
        result = CorrectionWorkflow(
            self.corrector, self.ledger, verifier, "isolated-test-adapter"
        ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["verified"])
        self.assertFalse(result["applied"])
        verifier.assert_called_once_with(
            source=SOURCE, filename="candidate.py", source_sha256=digest
        )
        saved = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "VERIFIED")
        self.assertEqual(saved["verification"]["source_sha256"], digest)
        self.assertEqual(saved["verification"]["verifier_id"], "isolated-test-adapter")
        self.assertEqual(saved["verification"]["run_id"], "run-0001")

    def test_workflow_and_docker_verifier_integrate_with_mocked_container(self):
        verifier = DockerFunctionVerifier(
            "add",
            [
                {"args": [1, 2], "kwargs": {}, "expected": 3},
                {"args": [-2, 5], "kwargs": {}, "expected": 3},
            ],
            image="python:3.12-slim",
        )
        summary = "JARVIS_VERIFIER_RESULT=" + json.dumps({
            "status": "passed", "test_count": 2,
            "passed_count": 2, "failed_count": 0, "failures": [],
        })
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[(0, "", False, False), (0, summary, False, False)],
        ):
            result = CorrectionWorkflow(
                self.corrector, self.ledger, verifier, verifier.verifier_id
            ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["verified"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["ledger_record"]["status"], "VERIFIED")
        self.assertEqual(
            result["ledger_record"]["verification"]["verifier_id"],
            verifier.verifier_id,
        )

    def _evidence(self, source_hash, status="passed", verifier_id="isolated-test-adapter"):
        return {
            "status": status, "source_sha256": source_hash, "verifier_id": verifier_id,
            "run_id": "run-0002", "checks_performed": ["behavioral_tests"],
            "commands": ["python -m unittest test_candidate"], "exit_code": 0,
            "test_count": 1, "timestamp": "2026-10-22T00:00:00Z",
        }

    def test_verifier_must_match_candidate_hash(self):
        verifier = Mock(return_value=self._evidence("0" * 64))
        result = CorrectionWorkflow(
            self.corrector, self.ledger, verifier, "isolated-test-adapter"
        ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "behavior_failed")
        self.assertFalse(result["verified"])
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")

    def test_failed_verifier_never_creates_verified_record(self):
        digest = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        verifier = Mock(return_value=self._evidence(digest, status="failed"))
        result = CorrectionWorkflow(
            self.corrector, self.ledger, verifier, "isolated-test-adapter"
        ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "behavior_failed")
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")

    def test_verifier_exception_is_bounded_and_recorded_unverified(self):
        verifier = Mock(side_effect=TimeoutError("private diagnostic"))
        result = CorrectionWorkflow(
            self.corrector, self.ledger, verifier, "isolated-test-adapter"
        ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "verification_error")
        self.assertEqual(result["behavioral_verification"]["error_type"], "TimeoutError")
        self.assertNotIn("private diagnostic", str(result))
        self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")

    def test_invalid_or_timezone_naive_timestamp_never_verifies(self):
        digest = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        for timestamp in ("", "not-a-timestamp", "2026-10-22T00:00:00"):
            with self.subTest(timestamp=timestamp):
                evidence = self._evidence(digest)
                evidence["timestamp"] = timestamp
                verifier = Mock(return_value=evidence)
                result = CorrectionWorkflow(
                    self.corrector, self.ledger, verifier, "isolated-test-adapter"
                ).run("Implement add", "pass", "AssertionError: expected sum")
                self.assertEqual(result["status"], "behavior_failed")
                self.assertFalse(result["verified"])
                self.assertEqual(result["ledger_record"]["status"], "UNVERIFIED")

    def test_verifier_identity_must_match_configured_adapter(self):
        digest = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        verifier = Mock(return_value=self._evidence(digest, verifier_id="other"))
        result = CorrectionWorkflow(
            self.corrector, self.ledger, verifier, "isolated-test-adapter"
        ).run("Implement add", "pass", "AssertionError: expected sum")
        self.assertEqual(result["status"], "behavior_failed")
        self.assertFalse(result["verified"])

    def test_invalid_error_category_falls_back_to_unknown(self):
        self.corrector.propose.return_value["error_category"] = []
        result = CorrectionWorkflow(self.corrector, self.ledger).run(
            "Implement add", "pass", "AssertionError: expected sum"
        )
        self.assertEqual(result["ledger_record"]["category"], "unknown")
        self.assertEqual(result["ledger_record"]["status"], "SYNTAX_VALID")

    def test_verifier_configuration_requires_identity(self):
        with self.assertRaises(ValueError):
            CorrectionWorkflow(self.corrector, self.ledger, lambda **kwargs: {}, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
