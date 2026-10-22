"""Tests for the append-only learning ledger."""

import json
import tempfile
import unittest
from pathlib import Path

from src.learning_ledger import LearningLedger, LearningLedgerError


HASH = "a" * 64
VALID_EVIDENCE = {
    "commands": ["python -m unittest tests.test_example -v"],
    "exit_code": 0,
    "test_count": 4,
    "timestamp": "2026-10-21T02:00:00Z",
    "source_sha256": HASH,
    "verifier_id": "isolated-test-adapter",
    "run_id": "run-0001",
    "checks_performed": ["behavioral_tests"],
}


class LearningLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "learning.jsonl"
        self.ledger = LearningLedger(self.path)

    def test_default_record_is_unverified_and_omits_source(self):
        record = self.ledger.append_record(
            HASH, "syntax_error", "Parser failed near line 12"
        )
        self.assertEqual(record["status"], "UNVERIFIED")
        self.assertEqual(record["schema_version"], 2)
        self.assertNotIn("source", record)
        self.assertNotIn("failure_output", record)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["source_sha256"], HASH)

    def test_verified_requires_successful_test_evidence(self):
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record(
                HASH, "test_error", "fixed", status="VERIFIED"
            )

    def test_verified_record_accepts_explicit_evidence(self):
        record = self.ledger.append_record(
            HASH, "test_error", "Regression covered",
            status="VERIFIED", verification=VALID_EVIDENCE,
        )
        self.assertEqual(record["status"], "VERIFIED")
        self.assertEqual(record["verification"]["exit_code"], 0)
        self.assertEqual(record["verification"]["test_count"], 4)
        self.assertEqual(record["verification"]["verifier_id"], "isolated-test-adapter")
        self.assertEqual(record["verification"]["run_id"], "run-0001")
        self.assertEqual(record["verification"]["source_sha256"], HASH)
        self.assertIn("behavioral_tests", record["verification"]["checks_performed"])

    def test_verified_record_rejects_mismatched_source_hash(self):
        evidence = dict(VALID_EVIDENCE, source_sha256="b" * 64)
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record(
                HASH, "test_error", "hash mismatch",
                status="VERIFIED", verification=evidence,
            )

    def test_verified_record_requires_behavioral_test_evidence(self):
        evidence = dict(VALID_EVIDENCE, checks_performed=["python_syntax"])
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record(
                HASH, "test_error", "syntax is not behavioral verification",
                status="VERIFIED", verification=evidence,
            )

    def test_nonzero_exit_code_is_rejected(self):
        evidence = dict(VALID_EVIDENCE, exit_code=1)
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record(
                HASH, "test_error", "not fixed",
                status="VERIFIED", verification=evidence,
            )

    def test_invalid_hash_is_rejected(self):
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record("not-a-hash", "unknown", "lesson")

    def test_unrecognized_category_is_rejected(self):
        with self.assertRaises(LearningLedgerError):
            self.ledger.append_record(HASH, "arbitrary", "lesson")

    def test_common_secret_like_text_is_redacted(self):
        record = self.ledger.append_record(
            HASH, "unknown", "api_key=ABC123 should not persist"
        )
        self.assertNotIn("ABC123", record["summary"])
        self.assertIn("[REDACTED]", record["summary"])

    def test_records_are_appended_without_overwriting(self):
        self.ledger.append_record(HASH, "syntax_error", "first")
        self.ledger.append_record(HASH, "syntax_error", "second")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["summary"], "first")
        self.assertEqual(json.loads(lines[1])["summary"], "second")


if __name__ == "__main__":
    unittest.main(verbosity=2)
