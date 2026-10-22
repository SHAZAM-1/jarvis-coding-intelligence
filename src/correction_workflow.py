"""Coordinate proposal, syntax checks, and explicit opt-in behavioral verification.

The normal run remains non-executing. Behavioral execution is a separate method
that requires explicit opt-in and a configured Docker verifier.
"""

import hashlib
import re

from src.behavioral_verifier import (
    BehavioralVerificationError,
    VerificationUnavailableError,
)
from src.verification_runner import verify_python_source


_PYTHON_BLOCK = re.compile(
    r"```python[ \t]*\r?\n(.*?)\r?\n?```", re.IGNORECASE | re.DOTALL
)


def extract_python_candidate(proposal):
    """Return one explicitly fenced Python candidate, or None if ambiguous."""
    if not isinstance(proposal, str):
        return None
    matches = _PYTHON_BLOCK.findall(proposal)
    if len(matches) != 1:
        return None
    candidate = matches[0]
    if not candidate.strip():
        return None
    return candidate if candidate.endswith("\n") else candidate + "\n"


class CorrectionWorkflow:
    """Run bounded proposal -> syntax verification -> evidence-labelled ledger."""

    def __init__(self, corrector, ledger, behavioral_verifier=None):
        if not callable(getattr(corrector, "propose", None)):
            raise TypeError("corrector must provide a callable propose method")
        if not callable(getattr(ledger, "append_record", None)):
            raise TypeError("ledger must provide a callable append_record method")
        if not callable(getattr(ledger, "append_syntax_valid_record", None)):
            raise TypeError(
                "ledger must independently validate syntax-valid records"
            )
        if behavioral_verifier is not None and not callable(
            getattr(behavioral_verifier, "verify", None)
        ):
            raise TypeError(
                "behavioral_verifier must provide a callable verify method"
            )
        self.corrector = corrector
        self.ledger = ledger
        self.behavioral_verifier = behavioral_verifier

    def run(self, task, current_code, failure_output, filename="candidate.py"):
        """Propose a fix, parse a single candidate, and record only supported status.

        Candidate code is never executed or written to a project file. If the
        proposal lacks exactly one fenced Python block, the result remains
        UNVERIFIED. Syntax-valid candidates are recorded as SYNTAX_VALID only.
        """
        proposal_result = self.corrector.propose(
            task=task,
            current_code=current_code,
            failure_output=failure_output,
        )
        proposal_text = proposal_result.get("proposal")
        candidate = extract_python_candidate(proposal_text)

        if candidate is None:
            source_hash = hashlib.sha256(current_code.encode("utf-8")).hexdigest()
            ledger_record = self.ledger.append_record(
                source_sha256=source_hash,
                category=proposal_result.get("error_category", "unknown"),
                summary=(
                    "No unambiguous, non-empty fenced Python candidate was "
                    "provided; syntax verification was not performed."
                ),
                status="UNVERIFIED",
            )
            return {
                "status": "candidate_missing_or_ambiguous",
                "proposal_result": proposal_result,
                "candidate_source": None,
                "verification": None,
                "ledger_record": ledger_record,
                "applied": False,
                "executed": False,
                "behaviorally_verified": False,
            }

        verification = verify_python_source(candidate, filename=filename)
        category = proposal_result.get("error_category", "unknown")
        if verification["syntax_valid"]:
            summary = "Candidate passed Python syntax parsing only."
            # The ledger independently parses the same candidate before it
            # allows a SYNTAX_VALID record.
            ledger_record = self.ledger.append_syntax_valid_record(
                source=candidate,
                category=category,
                summary=summary,
            )
        else:
            summary = "Candidate failed Python syntax parsing."
            ledger_record = self.ledger.append_record(
                source_sha256=verification["sha256"],
                category=category,
                summary=summary,
                status="UNVERIFIED",
            )
        return {
            "status": verification["status"],
            "proposal_result": proposal_result,
            "candidate_source": candidate,
            "verification": verification,
            "ledger_record": ledger_record,
            "applied": False,
            "executed": False,
            "behaviorally_verified": False,
        }

    def verify_behavior(
        self, candidate_source, entrypoint, cases, *, allow_execution=False,
        category="other",
    ):
        """Run optional Docker behavioral checks and record only supported status.

        This method is never called automatically by run(). It requires both a
        configured verifier and explicit allow_execution=True.
        """
        if self.behavioral_verifier is None:
            raise VerificationUnavailableError(
                "No behavioral verifier is configured; syntax-only mode remains active."
            )
        if allow_execution is not True:
            raise VerificationUnavailableError(
                "Behavioral execution is disabled; explicitly opt in to enable it."
            )

        result = self.behavioral_verifier.verify(
            candidate_source,
            entrypoint,
            cases,
            allow_execution=True,
        )
        receipt = result.receipt
        source_hash = hashlib.sha256(candidate_source.encode("utf-8")).hexdigest()
        if receipt.source_sha256 != source_hash:
            raise BehavioralVerificationError(
                "Verifier receipt does not match the proposed candidate source."
            )
        if receipt.success is True:
            summary = (
                f"All {receipt.case_count} declared behavioral cases passed "
                "in the configured Docker sandbox."
            )
            ledger_record = self.ledger.append_verified_record(
                source=candidate_source,
                category=category,
                summary=summary,
                receipt=receipt,
            )
            status = "verified"
        else:
            summary = (
                f"Behavioral verification failed: {receipt.passed_count} of "
                f"{receipt.case_count} declared cases passed."
            )
            ledger_record = self.ledger.append_record(
                source_sha256=receipt.source_sha256,
                category=category,
                summary=summary,
                status="UNVERIFIED",
            )
            status = "behavioral_failed"

        return {
            "status": status,
            "verification_result": result,
            "ledger_record": ledger_record,
            "applied": False,
            "executed": True,
            "behaviorally_verified": receipt.success is True,
        }
