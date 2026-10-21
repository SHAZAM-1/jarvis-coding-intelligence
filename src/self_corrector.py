"""Bounded, proposal-only code correction."""

from src.error_analyzer import analyze_error


class CorrectionLimitReached(RuntimeError):
    """Raised when a correction session reaches its attempt limit."""


class SelfCorrector:
    """Generate correction proposals without applying or executing them."""

    def __init__(self, client, max_attempts=2):
        if (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or not 1 <= max_attempts <= 2
        ):
            raise ValueError("max_attempts must be either 1 or 2")
        self.client = client
        self.max_attempts = max_attempts
        self.attempts_used = 0

    def propose(self, task, current_code, failure_output):
        """Return a proposal; never write project files."""
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if not isinstance(current_code, str):
            raise TypeError("current_code must be a string")
        if not isinstance(failure_output, str):
            raise TypeError("failure_output must be a string")
        if not failure_output.strip():
            raise ValueError(
                "failure_output must contain the actual failure"
            )
        if self.attempts_used >= self.max_attempts:
            raise CorrectionLimitReached(
                "Correction attempt limit reached. Review the evidence "
                "before starting a new session."
            )

        report = analyze_error(failure_output)
        next_attempt = self.attempts_used + 1
        prompt = f"""
You are the correction component of Jarvis Coding Intelligence.
Produce a cautious, evidence-based code correction proposal.

Attempt: {next_attempt} of {self.max_attempts}
CODING TASK:
{task}
CURRENT CODE:
{current_code}
ERROR CATEGORY:
{report["category"]}
ERROR SUMMARY:
{report["summary"]}
ACTUAL FAILURE OUTPUT:
{report["evidence"]}

REQUIREMENTS:
1. Explain the likely cause and distinguish facts from hypotheses.
2. Propose the smallest reasonable correction.
3. Return the complete replacement for the relevant code unit.
4. Include regression tests for this failure.
5. Never claim tests passed unless actually executed.
6. Do not invent files, dependencies, APIs, or test results.
7. If evidence is insufficient, say what information is missing.
8. Do not request credentials, secrets, or unrelated private files.
9. Do not suggest destructive Git operations.
10. This is a proposal only; do not claim to have changed files.

Structure your answer as:
CAUSE:
PROPOSED FIX:
REGRESSION TESTS:
VERIFICATION REQUIRED:
UNCERTAINTIES:
""".strip()

        self.attempts_used = next_attempt
        proposal = self.client.generate(prompt)
        return {
            "attempt": next_attempt,
            "maximum_attempts": self.max_attempts,
            "error_category": report["category"],
            "proposal": proposal,
            "verified": False,
            "applied": False,
        }
