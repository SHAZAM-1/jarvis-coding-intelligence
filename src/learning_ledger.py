"""Append-only ledger for compact lessons with conservative evidence labels.

Only the dedicated syntax-recording method may set SYNTAX_VALID, and it parses
the source itself. VERIFIED requires a receipt from the Docker behavioral
verifier; real sandbox integration remains unverified.
"""

import hashlib
import json
import math
import os
import re
import threading
from collections import deque
from datetime import datetime

from src.verification_runner import verify_python_source


STATUSES = {"UNVERIFIED", "SYNTAX_VALID", "VERIFIED"}
MAX_LEDGER_LINE_CHARS = 8192
MAX_LEDGER_SCAN_RECORDS = 1000
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


def _valid_stored_verified_record(record):
    """Validate the persisted evidence shape; the local JSONL is not tamper-proof."""
    if (
        not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record.get("schema_version") != 1
    ):
        return False
    if record.get("status") != "VERIFIED":
        return False
    try:
        source_hash = _validate_hash(record.get("source_sha256"))
    except LearningLedgerError:
        return False
    category = record.get("category")
    if (
        not isinstance(category, str)
        or category not in _CATEGORIES
        or not isinstance(record.get("summary"), str)
        or len(record["summary"]) > 240
    ):
        return False
    evidence = record.get("verification")
    if not isinstance(evidence, dict):
        return False
    required = {
        "source_sha256", "manifest_sha256", "image_digest", "sandbox_policy",
        "case_count", "answered_count", "passed_count", "failed_count",
        "exit_code", "elapsed_seconds", "timestamp", "success",
    }
    if set(evidence) != required:
        return False
    if evidence.get("source_sha256") != source_hash:
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("manifest_sha256", ""))):
        return False
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9./:_-]*@sha256:[0-9a-f]{64}",
        str(evidence.get("image_digest", "")),
    ):
        return False
    if evidence.get("sandbox_policy") != "docker-json-callable-v1":
        return False
    case_count = evidence.get("case_count")
    answered_count = evidence.get("answered_count")
    passed_count = evidence.get("passed_count")
    failed_count = evidence.get("failed_count")
    exit_code = evidence.get("exit_code")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (
            case_count, answered_count, passed_count, failed_count, exit_code
        )
    ):
        return False
    if (
        case_count < 1
        or answered_count != case_count
        or passed_count != case_count
        or failed_count != 0
        or exit_code != 0
        or evidence.get("success") is not True
    ):
        return False
    elapsed = evidence.get("elapsed_seconds")
    if (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        return False
    for timestamp in (record.get("recorded_at"), evidence.get("timestamp")):
        if not isinstance(timestamp, str):
            return False
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return False
    return True


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
                "VERIFIED requires append_verified_record with a receipt "
                "from a trusted behavioral verifier."
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

    def find_verified_lessons(self, category=None, limit=5):
        """Return recent, structurally valid VERIFIED lessons without source code.

        The JSONL file is local data, not a tamper-proof database. This method
        validates record structure and receipt consistency but cannot prove a
        manually edited file was written by a real verifier.
        """
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 20
        ):
            raise ValueError("limit must be an integer between 1 and 20.")
        if category is not None and (
            not isinstance(category, str) or category not in _CATEGORIES
        ):
            raise LearningLedgerError("category must be a recognized diagnostic category.")
        if not os.path.exists(self.path):
            return []

        tail = deque(maxlen=MAX_LEDGER_SCAN_RECORDS)
        try:
            with open(
                self.path, "r", encoding="utf-8", errors="replace"
            ) as stream:
                while True:
                    line = stream.readline(MAX_LEDGER_LINE_CHARS + 1)
                    if not line:
                        break
                    if len(line) > MAX_LEDGER_LINE_CHARS:
                        while line and not line.endswith("\n"):
                            line = stream.readline(MAX_LEDGER_LINE_CHARS + 1)
                        tail.append(None)
                    else:
                        tail.append(line)
        except OSError as exc:
            raise LearningLedgerError("Could not read the learning ledger.") from exc

        lessons = []
        for line in tail:
            if not line:
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if not _valid_stored_verified_record(record):
                continue
            if category is not None and record["category"] != category:
                continue
            lessons.append(record)
        return lessons[-limit:][::-1]

    def append_verified_record(self, source, category, summary, receipt):
        """Record VERIFIED only from a verifier-issued receipt bound to source."""
        from src.behavioral_verifier import SANDBOX_POLICY, is_trusted_receipt

        verification = verify_python_source(source)
        if not verification["syntax_valid"]:
            raise LearningLedgerError(
                "Cannot record VERIFIED: source failed syntax verification."
            )
        if not is_trusted_receipt(receipt):
            raise LearningLedgerError(
                "VERIFIED requires a receipt issued by BehavioralVerifier."
            )
        if receipt.source_sha256 != verification["sha256"]:
            raise LearningLedgerError(
                "Verification receipt does not match the supplied source hash."
            )
        if (
            receipt.success is not True
            or receipt.exit_code != 0
            or receipt.case_count < 1
            or receipt.answered_count != receipt.case_count
            or receipt.passed_count != receipt.case_count
            or receipt.failed_count != 0
            or receipt.sandbox_policy != SANDBOX_POLICY
            or not receipt.manifest_sha256
            or not receipt.image_digest
        ):
            raise LearningLedgerError(
                "VERIFIED requires a complete successful behavioral "
                "verification receipt."
            )
        return self._append_record(
            verification["sha256"],
            category,
            summary,
            status="VERIFIED",
            verification=receipt.to_dict(),
        )

    def _append_record(
        self, source_sha256, category, summary, status, verification=None
    ):
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
        if status == "VERIFIED":
            if not isinstance(verification, dict):
                raise LearningLedgerError(
                    "VERIFIED records require verifier-issued evidence."
                )
            record["verification"] = verification
        elif verification is not None:
            raise LearningLedgerError(
                "Verification evidence is accepted only for VERIFIED records."
            )
        encoded = json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n"
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        with _WRITE_LOCK:
            with open(self.path, "a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        return record
