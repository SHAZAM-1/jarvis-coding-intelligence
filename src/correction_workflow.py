"""Coordinate proposal, non-executing syntax checks, and cautious lesson recording.

This workflow deliberately does not execute model-generated code. A syntax-valid
candidate is not a behaviorally verified fix, and no VERIFIED ledger status is
issued by this module.
"""

import hashlib
import re

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

    def __init__(self, corrector, ledger):
        if not callable(getattr(corrector, "propose", None)):
            raise TypeError("corrector must provide a callable propose method")
        if not callable(getattr(ledger, "append_record", None)):
            raise TypeError("ledger must provide a callable append_record method")
        self.corrector = corrector
        self.ledger = ledger

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
        status = (
            "SYNTAX_VALID" if verification["syntax_valid"] else "UNVERIFIED"
        )
        summary = (
            "Candidate passed Python syntax parsing only."
            if verification["syntax_valid"]
            else "Candidate failed Python syntax parsing."
        )
        ledger_record = self.ledger.append_record(
            source_sha256=verification["sha256"],
            category=proposal_result.get("error_category", "unknown"),
            summary=summary,
            status=status,
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
