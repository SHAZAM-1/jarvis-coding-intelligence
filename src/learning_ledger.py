"""Append-only ledger for compact, evidence-labelled coding lessons.

The ledger records caller-supplied verification metadata. It does not itself
execute tests or prove that a command was genuinely run.
"""

import hashlib
import json
import os
import re
import threading
from datetime import datetime


STATUSES = {"UNVERIFIED", "SYNTAX_VALID", "VERIFIED"}
_CATEGORIES = {
    "missing_import", "syntax_error", "missing_attribute", "missing_key",
    "type_error", "assertion_failure", "timeout", "connection_error",
    "test_error", "unknown", "other",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"),
)
_WRITE_LOCK = threading.Lock()


class LearningLedgerError(ValueError):
    """Raised when a ledger record is incomplete or unsafe."""


def _safe_text(value, maximum):
    """Remove control characters and redact common secret-like assignments."""
    if not isinstance(value, str):
        raise LearningLedgerError("Text fields must be strings.")
    text = "".join(ch for ch in value if ch.isprintable()).strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:maximum]


def _validate_hash(source_sha256):
    if (
        not isinstance(source_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
    ):
        raise LearningLedgerError("source_sha256 must be a lowercase SHA-256 hex digest.")
    return source_sha256


def _verification_evidence(evidence):
    if not isinstance(evidence, dict):
        raise LearningLedgerError("VERIFIED records require verification evidence.")

    commands = evidence.get("commands")
    exit_code = evidence.get("exit_code")
    test_count = evidence.get("test_count")
    timestamp = evidence.get("timestamp")

    if (
        not isinstance(commands, list)
        or not commands
        or any(not isinstance(command, str) or not command.strip() for command in commands)
    ):
        raise LearningLedgerError("Verification requires at least one test command.")
    if exit_code != 0 or isinstance(exit_code, bool):
        raise LearningLedgerError("Verification requires exit_code=0.")
    if not isinstance(test_count, int) or isinstance(test_count, bool) or test_count < 1:
        raise LearningLedgerError("Verification requires test_count >= 1.")
    if not isinstance(timestamp, str):
        raise LearningLedgerError("Verification requires an ISO timestamp.")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LearningLedgerError("Verification timestamp must be ISO-8601.") from exc

    return {
        "commands": [_safe_text(command, 200) for command in commands[:3]],
        "exit_code": 0,
        "test_count": test_count,
        "timestamp": timestamp,
    }


class LearningLedger:
    """Append compact, privacy-conscious lesson records as JSON Lines."""

    def __init__(self, path="data/learning_ledger.jsonl"):
        if not isinstance(path, (str, os.PathLike)) or not str(path).strip():
            raise ValueError("Ledger path must be a non-empty path.")
        self.path = os.fspath(path)

    def append_record(
        self,
        source_sha256,
        category,
        summary,
        status="UNVERIFIED",
        verification=None,
    ):
        """Append one record; raw source and raw failure output are never stored."""
        if status not in STATUSES:
            raise LearningLedgerError(f"status must be one of {sorted(STATUSES)}")
        source_sha256 = _validate_hash(source_sha256)
        if not isinstance(category, str) or category not in _CATEGORIES:
            raise LearningLedgerError("category must be a recognized diagnostic category.")

        record = {
            "schema_version": 1,
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source_sha256": source_sha256,
            "category": category,
            "summary": _safe_text(summary, 240),
            "status": status,
        }
        if status == "VERIFIED":
            record["verification"] = _verification_evidence(verification)
        elif verification is not None:
            # Preserve evidence only for explicitly verified records, avoiding
            # misleading partial proof on other statuses.
            raise LearningLedgerError(
                "verification evidence is accepted only for VERIFIED records."
            )

        encoded = (json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        with _WRITE_LOCK:
            with open(self.path, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        return record
