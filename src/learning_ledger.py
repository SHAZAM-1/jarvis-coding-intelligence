"""Append-only ledger for compact lessons with conservative evidence labels.

Only workflow-produced syntax checks may set SYNTAX_VALID. This ledger does not
execute candidate code, and VERIFIED is reserved until a trusted behavioral
verifier can produce its own evidence.
"""

import hashlib
import json
import os
import re
import threading
from datetime import datetime

from src.verification_runner import verify_python_source


STATUSES = {"UNVERIFIED", "SYNTAX_VALID"}
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
        """Append an UNVERIFIED record; caller-supplied proof is never trusted."""
        if status == "VERIFIED":
            raise LearningLedgerError(
                "VERIFIED status is reserved until a trusted behavioral "
                "verifier can supply its own evidence."
            )
        if status != "UNVERIFIED":
            raise LearningLedgerError(
                "Only UNVERIFIED may be requested directly; use "
                "append_syntax_valid_record for independently parsed source."
            )
        if verification is not None:
            raise LearningLedgerError(
                "Caller-supplied verification evidence is not accepted."
            )
        return self._append_record(
            source_sha256, category, summary, status="UNVERIFIED"
        )

    def append_syntax_valid_record(self, source, category, summary):
        """Independently parse source before allowing a SYNTAX_VALID record."""
        verification = verify_python_source(source)
        if not verification["syntax_valid"]:
            raise LearningLedgerError(
                "Cannot record SYNTAX_VALID: Python syntax parsing failed."
            )
        return self._append_record(
            verification["sha256"], category, summary, status="SYNTAX_VALID"
        )

    def _append_record(self, source_sha256, category, summary, status):
        """Persist a validated record without storing source or failure output."""
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
        encoded = json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n"
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        with _WRITE_LOCK:
            with open(self.path, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        return record
