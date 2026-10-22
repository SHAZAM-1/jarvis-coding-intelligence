"""Tests for the append-only learning ledger."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.learning_ledger import LearningLedger, LearningLedgerError


HASH = "a" * 64


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
        self.assertNotIn("source", record)
        self.assertNotIn("failure_output", record)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["source_sha256"], HASH)

    def test_verified_status_is_reserved_for_trusted_behavioral_verifier(self):
        with self.assertRaisesRegex(
            LearningLedgerError, "trusted behavioral verifier"
        ):
            self.ledger.append_record(
                HASH, "test_error", "fixed", status="VERIFIED"
            )

    def test_direct_syntax_valid_status_is_rejected(self):
        with self.assertRaisesRegex(
            LearningLedgerError, "append_syntax_valid_record"
        ):
            self.ledger.append_record(
                HASH, "syntax_error", "claimed syntax pass",
                status="SYNTAX_VALID",
            )

    def test_ledger_independently_parses_before_syntax_valid_status(self):
        source = "def add(a, b):\n    return a + b\n"
        record = self.ledger.append_syntax_valid_record(
            source, "assertion_failure", "Syntax checked by ledger"
        )
        self.assertEqual(record["status"], "SYNTAX_VALID")
        self.assertEqual(
            record["source_sha256"],
            hashlib.sha256(source.encode("utf-8")).hexdigest(),
        )

    def test_ledger_rejects_invalid_source_for_syntax_valid_status(self):
        with self.assertRaisesRegex(LearningLedgerError, "syntax parsing failed"):
            self.ledger.append_syntax_valid_record(
                "def add(:\n    return 1\n",
                "syntax_error",
                "This source is invalid",
            )

    def test_caller_supplied_verification_evidence_is_rejected(self):
        evidence = {
            "commands": ["python -m unittest"],
            "exit_code": 0,
            "test_count": 4,
            "timestamp": "2026-10-21T02:00:00Z",
        }
        with self.assertRaisesRegex(LearningLedgerError, "Caller-supplied"):
            self.ledger.append_record(
                HASH, "test_error", "claimed pass",
                status="UNVERIFIED", verification=evidence,
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
