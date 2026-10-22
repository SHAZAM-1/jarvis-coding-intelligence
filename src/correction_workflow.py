"""Safe orchestration for correction proposals, verification, and learning.

This module never writes or executes model-generated code. Behavioral checks
are delegated to a configured trusted verifier adapter. Without that adapter,
syntax-valid candidates are never marked VERIFIED.
"""
import re

from src.learning_ledger import LearningLedgerError
from src.verification_runner import verify_python_source

_ALLOWED_CATEGORIES = {
    "missing_import", "syntax_error", "missing_attribute", "missing_key",
    "type_error", "assertion_failure", "timeout", "connection_error",
    "test_error", "unknown", "other",
}
_FENCED_BLOCK = re.compile(r"(?s)```([^\n`]*)\n(.*?)```")


class ProposalExtractionError(ValueError):
    """A model proposal has no single, unambiguous Python replacement."""


def extract_candidate_source(proposal):
    """Extract exactly one Python code block from PROPOSED FIX."""
    if not isinstance(proposal, str):
        raise ProposalExtractionError("Proposal must be text.")
    start = re.search(r"(?im)^PROPOSED FIX:\s*$", proposal)
    if start is None:
        raise ProposalExtractionError("Proposal has no PROPOSED FIX section.")
    tail = proposal[start.end():]
    end = re.search(r"(?im)^REGRESSION TESTS:\s*$", tail)
    if end is None:
        raise ProposalExtractionError("Proposal has no REGRESSION TESTS boundary.")
    blocks = _FENCED_BLOCK.findall(tail[:end.start()])
    if len(blocks) != 1 or blocks[0][0].strip().lower() not in {"python", "py"}:
        raise ProposalExtractionError(
            "PROPOSED FIX must contain exactly one fenced Python code block."
        )
    source = blocks[0][1]
    if not source.strip():
        raise ProposalExtractionError("Proposed Python source is empty.")
    return source.strip("\r\n") + "\n"


def _is_verified_evidence(result, source_sha256, expected_verifier_id):
    """Check that a trusted verifier reports success for this exact source."""
    if not isinstance(result, dict) or result.get("status") != "passed":
        return False
    if result.get("source_sha256") != source_sha256:
        return False
    if result.get("verifier_id") != expected_verifier_id:
        return False
    if not isinstance(result.get("run_id"), str) or not result["run_id"].strip():
        return False
    checks = result.get("checks_performed")
    if not isinstance(checks, list) or "behavioral_tests" not in checks:
        return False
    commands = result.get("commands")
    if not isinstance(commands, list) or not commands or any(
        not isinstance(item, str) or not item.strip() for item in commands
    ):
        return False
    code = result.get("exit_code")
    if not isinstance(code, int) or isinstance(code, bool) or code != 0:
        return False
    count = result.get("test_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        return False
    return isinstance(result.get("timestamp"), str)


class CorrectionWorkflow:
    """Coordinate one proposal through syntax checks and evidence recording."""

    def __init__(self, corrector, ledger, behavioral_verifier=None, verifier_id=None):
        if not callable(getattr(corrector, "propose", None)):
            raise TypeError("corrector must provide a callable propose method")
        if not callable(getattr(ledger, "append_record", None)):
            raise TypeError("ledger must provide a callable append_record method")
        if behavioral_verifier is not None and not callable(behavioral_verifier):
            raise TypeError("behavioral_verifier must be callable")
        if behavioral_verifier is not None:
            if not isinstance(verifier_id, str) or not verifier_id.strip():
                raise ValueError("verifier_id is required with a behavioral verifier")
        elif verifier_id is not None:
            raise ValueError("verifier_id requires a behavioral_verifier")
        self.corrector = corrector
        self.ledger = ledger
        self.behavioral_verifier = behavioral_verifier
        self.verifier_id = verifier_id.strip() if verifier_id else None

    def run(self, task, current_code, failure_output, filename="candidate.py"):
        """Propose, extract, syntax-check, optionally verify, and record.

        A configured verifier is trusted integration code and must independently
        test the exact source in a suitably restricted environment. This class
        never executes or applies candidate code itself.
        """
        proposal_result = self.corrector.propose(
            task=task, current_code=current_code, failure_output=failure_output
        )
        if not isinstance(proposal_result, dict):
            raise TypeError("corrector.propose must return a dictionary")
        proposal = proposal_result.get("proposal")
        try:
            source = extract_candidate_source(proposal)
        except ProposalExtractionError as exc:
            return {
                "status": "proposal_unparseable", "verified": False, "applied": False,
                "proposal": proposal, "candidate_source": None, "syntax": None,
                "behavioral_verification": {"status": "not_started", "reason": str(exc)},
                "ledger_record": None,
            }

        syntax = verify_python_source(source, filename=filename)
        category = proposal_result.get("error_category")
        if not isinstance(category, str) or category not in _ALLOWED_CATEGORIES:
            category = "unknown"

        if not syntax["syntax_valid"]:
            record = self.ledger.append_record(
                syntax["sha256"], category,
                "Correction proposal failed Python syntax validation.",
                status="UNVERIFIED",
            )
            return {
                "status": "syntax_invalid", "verified": False, "applied": False,
                "proposal": proposal, "candidate_source": source, "syntax": syntax,
                "behavioral_verification": {"status": "not_started"},
                "ledger_record": record,
            }

        if self.behavioral_verifier is None:
            record = self.ledger.append_record(
                syntax["sha256"], category,
                "Syntax valid; behavioral verification was not configured.",
                status="SYNTAX_VALID",
            )
            return {
                "status": "syntax_valid", "verified": False, "applied": False,
                "proposal": proposal, "candidate_source": source, "syntax": syntax,
                "behavioral_verification": {"status": "not_configured"},
                "ledger_record": record,
            }

        try:
            evidence = self.behavioral_verifier(
                source=source, filename=filename, source_sha256=syntax["sha256"]
            )
        except Exception as exc:
            record = self.ledger.append_record(
                syntax["sha256"], category,
                "Syntax valid; behavioral verification did not complete.",
                status="UNVERIFIED",
            )
            return {
                "status": "verification_error", "verified": False, "applied": False,
                "proposal": proposal, "candidate_source": source, "syntax": syntax,
                "behavioral_verification": {
                    "status": "error", "error_type": type(exc).__name__
                },
                "ledger_record": record,
            }

        if _is_verified_evidence(evidence, syntax["sha256"], self.verifier_id):
            ledger_evidence = {
                key: evidence[key] for key in (
                    "commands", "exit_code", "test_count", "timestamp",
                    "source_sha256", "verifier_id", "run_id", "checks_performed",
                )
            }
            try:
                record = self.ledger.append_record(
                    syntax["sha256"], category,
                    "Correction passed syntax and trusted behavioral verification.",
                    status="VERIFIED", verification=ledger_evidence,
                )
            except LearningLedgerError:
                record = self.ledger.append_record(
                    syntax["sha256"], category,
                    "Syntax valid; verifier evidence failed ledger validation.",
                    status="UNVERIFIED",
                )
                return {
                    "status": "invalid_evidence", "verified": False, "applied": False,
                    "proposal": proposal, "candidate_source": source, "syntax": syntax,
                    "behavioral_verification": {"status": "invalid_evidence"},
                    "ledger_record": record,
                }
            return {
                "status": "verified", "verified": True, "applied": False,
                "proposal": proposal, "candidate_source": source, "syntax": syntax,
                "behavioral_verification": {
                    "status": "passed", "verifier_id": self.verifier_id,
                    "run_id": evidence["run_id"], "test_count": evidence["test_count"],
                },
                "ledger_record": record,
            }

        record = self.ledger.append_record(
            syntax["sha256"], category,
            "Syntax valid; behavioral verification failed or evidence did not match.",
            status="UNVERIFIED",
        )
        return {
            "status": "behavior_failed", "verified": False, "applied": False,
            "proposal": proposal, "candidate_source": source, "syntax": syntax,
            "behavioral_verification": {
                "status": "failed_or_invalid_evidence", "verifier_id": self.verifier_id
            },
            "ledger_record": record,
        }
