"""Unit tests for the opt-in Docker behavioral verifier; no Docker is invoked."""

import ast
import io
import json
from dataclasses import replace
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from src.learning_ledger import LearningLedger, LearningLedgerError
from src.behavioral_verifier import (
    MAX_OUTPUT_BYTES,
    _WORKER_SOURCE,
    BehavioralVerificationError,
    BehavioralVerifier,
    VerificationReceipt,
    VerificationUnavailableError,
    is_trusted_receipt,
)


IMAGE = "python:3.12-slim@sha256:" + ("a" * 64)
SOURCE = "def add(a, b):\n    return a + b\n"
CASES = [{"args": [1, 2], "kwargs": {}, "expected": 3}]


class FakeStdin:
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def write(self, value):
        self.data.extend(value)
        return len(value)

    def flush(self):
        return None

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, stdout=b'{"ok":true,"value":3}\n', stderr=b"", timeout=False):
        self.stdin = FakeStdin()
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = 0
        self.timeout_once = timeout
        self.killed = False

    def wait(self, timeout=None):
        if self.timeout_once:
            self.timeout_once = False
            raise subprocess.TimeoutExpired("docker run", timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class BehavioralVerifierTests(unittest.TestCase):
    def make_verifier(self, process=None, *, free_ram=4096, image_rc=0):
        self.process = process or FakeProcess()
        self.command = None

        def popen(command, **kwargs):
            self.command = command
            return self.process

        self.run_func = Mock(
            return_value=SimpleNamespace(returncode=image_rc, stdout="", stderr="")
        )
        return BehavioralVerifier(
            IMAGE,
            resource_probe=lambda: free_ram,
            run_func=self.run_func,
            popen_factory=popen,
        )

    def test_worker_harness_is_valid_python(self):
        ast.parse(_WORKER_SOURCE, filename="worker.py")

    def test_execution_is_disabled_by_default(self):
        verifier = self.make_verifier()
        with self.assertRaises(VerificationUnavailableError):
            verifier.verify(SOURCE, "add", CASES)
        self.run_func.assert_not_called()
        self.assertIsNone(self.command)

    def test_successful_cases_produce_verifier_issued_receipt(self):
        verifier = self.make_verifier()
        result = verifier.verify(SOURCE, "add", CASES, allow_execution=True)
        self.assertEqual(result.status, "verified")
        self.assertTrue(result.receipt.success)
        self.assertTrue(is_trusted_receipt(result.receipt))
        self.assertEqual(result.receipt.case_count, 1)
        self.assertEqual(result.receipt.answered_count, 1)
        self.assertEqual(result.receipt.passed_count, 1)
        self.assertEqual(result.receipt.failed_count, 0)
        self.assertEqual(result.failed_case_indices, ())
        self.assertEqual(self.command[1], "run")
        for flag in (
            "--pull=never", "--network=none", "--read-only", "--memory=256m",
            "--memory-swap=256m", "--cpus=0.5", "--pids-limit=32",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user=65534:65534",
        ):
            self.assertIn(flag, self.command)
        mount_index = self.command.index("--mount")
        self.assertTrue(self.command[mount_index + 1].endswith(",readonly"))
        sent = [json.loads(line) for line in self.process.stdin.data.splitlines()]
        self.assertEqual(sent, [{"args": [1, 2], "kwargs": {}}])
        self.assertNotIn("expected", sent[0])

        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "learning.jsonl")
            record = ledger.append_verified_record(
                SOURCE, "assertion_failure", "All declared cases passed",
                result.receipt,
            )
            self.assertEqual(record["status"], "VERIFIED")
            self.assertEqual(record["verification"]["case_count"], 1)
            stored = Path(directory, "learning.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("return a + b", stored)
            self.assertNotIn('"expected": 3', stored)

    def test_wrong_output_is_a_failed_behavioral_result(self):
        process = FakeProcess(b'{"ok":true,"value":4}\n')
        result = self.make_verifier(process).verify(
            SOURCE, "add", CASES, allow_execution=True
        )
        self.assertEqual(result.status, "behavioral_failed")
        self.assertFalse(result.receipt.success)
        self.assertEqual(result.receipt.passed_count, 0)
        self.assertEqual(result.receipt.failed_count, 1)
        self.assertEqual(result.failed_case_indices, (0,))
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "learning.jsonl")
            with self.assertRaisesRegex(LearningLedgerError, "successful behavioral"):
                ledger.append_verified_record(
                    SOURCE, "assertion_failure", "Must not be trusted",
                    result.receipt,
                )

    def test_receipt_cannot_verify_different_source(self):
        result = self.make_verifier().verify(
            SOURCE, "add", CASES, allow_execution=True
        )
        different_source = "def add(a, b):\\n    return a - b\\n"
        with tempfile.TemporaryDirectory() as directory:
            ledger = LearningLedger(Path(directory) / "learning.jsonl")
            with self.assertRaisesRegex(LearningLedgerError, "does not match"):
                ledger.append_verified_record(
                    different_source,
                    "assertion_failure",
                    "Must not be trusted",
                    result.receipt,
                )

    def test_candidate_exception_is_a_failed_case(self):
        process = FakeProcess(b'{"ok":false,"error":"ValueError"}\n')
        result = self.make_verifier(process).verify(
            SOURCE, "add", CASES, allow_execution=True
        )
        self.assertEqual(result.status, "behavioral_failed")
        self.assertEqual(result.receipt.failed_count, 1)

    def test_malformed_worker_output_fails_closed(self):
        process = FakeProcess(b"not-json\n")
        with self.assertRaises(BehavioralVerificationError):
            self.make_verifier(process).verify(
                SOURCE, "add", CASES, allow_execution=True
            )

    def test_non_boolean_protocol_status_fails_closed(self):
        process = FakeProcess(b'{"ok":1,"value":3}\n')
        with self.assertRaisesRegex(BehavioralVerificationError, "worker protocol"):
            self.make_verifier(process).verify(
                SOURCE, "add", CASES, allow_execution=True
            )

    def test_extra_worker_output_fails_closed(self):
        process = FakeProcess(
            b'{"ok":true,"value":3}\n{"ok":true,"value":3}\n'
        )
        with self.assertRaisesRegex(BehavioralVerificationError, "response count"):
            self.make_verifier(process).verify(
                SOURCE, "add", CASES, allow_execution=True
            )

    def test_timeout_requests_container_cleanup(self):
        process = FakeProcess(timeout=True)
        verifier = self.make_verifier(process)
        verifier.timeout_seconds = 0.01
        with self.assertRaisesRegex(BehavioralVerificationError, "timed out"):
            verifier.verify(SOURCE, "add", CASES, allow_execution=True)
        self.assertTrue(process.killed)
        self.assertEqual(self.run_func.call_count, 2)
        self.assertEqual(self.run_func.call_args.args[0][1:3], ["rm", "-f"])

    def test_output_limit_fails_closed_and_requests_cleanup(self):
        process = FakeProcess(b"x" * (MAX_OUTPUT_BYTES + 1))
        verifier = self.make_verifier(process)
        with self.assertRaisesRegex(BehavioralVerificationError, "output exceeded"):
            verifier.verify(SOURCE, "add", CASES, allow_execution=True)
        self.assertTrue(process.killed)
        self.assertEqual(self.run_func.call_count, 2)

    def test_missing_local_image_fails_without_running_candidate(self):
        verifier = self.make_verifier(image_rc=1)
        with self.assertRaisesRegex(
            VerificationUnavailableError, "not available locally"
        ):
            verifier.verify(SOURCE, "add", CASES, allow_execution=True)
        self.assertIsNone(self.command)

    def test_low_or_unknown_ram_fails_closed(self):
        for free_ram in (None, 100):
            with self.subTest(free_ram=free_ram):
                verifier = self.make_verifier(free_ram=free_ram)
                with self.assertRaises(VerificationUnavailableError):
                    verifier.verify(SOURCE, "add", CASES, allow_execution=True)
                self.run_func.assert_not_called()

    def test_invalid_source_or_entrypoint_is_rejected_before_docker(self):
        verifier = self.make_verifier()
        with self.assertRaises(ValueError):
            verifier.verify("def add(:", "add", CASES, allow_execution=True)
        with self.assertRaises(ValueError):
            verifier.verify(SOURCE, "../add", CASES, allow_execution=True)
        self.run_func.assert_not_called()

    def test_invalid_case_manifest_is_rejected_before_docker(self):
        verifier = self.make_verifier()
        invalid_cases = (
            [],
            [{"args": [], "kwargs": {}}],
            [{"args": [object()], "kwargs": {}, "expected": 1}],
        )
        for cases in invalid_cases:
            with self.subTest(cases=cases):
                with self.assertRaises(ValueError):
                    verifier.verify(SOURCE, "add", cases, allow_execution=True)
        self.run_func.assert_not_called()

    def test_bad_image_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            BehavioralVerifier("python:latest")

    def test_receipt_cannot_be_forged_by_constructing_the_dataclass(self):
        receipt = VerificationReceipt(
            source_sha256="a" * 64,
            manifest_sha256="b" * 64,
            image_digest=IMAGE,
            sandbox_policy="docker-json-callable-v1",
            case_count=1,
            answered_count=1,
            passed_count=1,
            failed_count=0,
            exit_code=0,
            elapsed_seconds=0.1,
            timestamp="2026-10-22T00:00:00Z",
            success=True,
        )
        self.assertFalse(is_trusted_receipt(receipt))

    def test_copying_a_receipt_does_not_preserve_issuer_authority(self):
        verifier = self.make_verifier()
        result = verifier.verify(SOURCE, "add", CASES, allow_execution=True)
        copied = replace(result.receipt, success=False)
        self.assertTrue(is_trusted_receipt(result.receipt))
        self.assertFalse(is_trusted_receipt(copied))


if __name__ == "__main__":
    unittest.main(verbosity=2)
