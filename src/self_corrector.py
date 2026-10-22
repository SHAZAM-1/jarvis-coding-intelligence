"""Bounded, proposal-only code correction with resource-aware reasoning."""

from src.error_analyzer import analyze_error
from src.resource_guard import available_memory_mb
from src.task_router import choose_profile


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
            raise ValueError("failure_output must contain the actual failure")
        if self.attempts_used >= self.max_attempts:
            raise CorrectionLimitReached(
                "Correction attempt limit reached. Review the evidence "
                "before starting a new session."
            )

        report = analyze_error(failure_output)
        next_attempt = self.attempts_used + 1
        profile = choose_profile(
            task,
            failure_output,
            available_ram_mb=available_memory_mb(),
        )
        prompt = f"""
You are the correction component of Jarvis Coding Intelligence.
Use careful, evidence-based reasoning, but do not expose hidden chain-of-thought.
Give a concise conclusion supported by concrete evidence. Separate facts,
hypotheses, and unknowns. Check edge cases and likely regressions before
recommending a fix.

Attempt: {next_attempt} of {self.max_attempts}
Reasoning budget: {profile}
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
1. Identify the likely root cause and distinguish facts from hypotheses.
2. Propose the smallest reasonable correction and explain why it addresses
   the observed failure.
3. Put the complete proposed Python replacement in exactly one fenced
   ```python code block. Do not include other Python code blocks. If you
   cannot provide a complete candidate, say so instead of inventing one.
4. Include focused regression tests and relevant edge cases outside the
   candidate code block.
5. Never claim tests passed unless actually executed.
6. Do not invent files, dependencies, APIs, or test results.
7. If evidence is insufficient, state exactly what is missing.
8. Do not request credentials, secrets, or unrelated private files.
9. Do not suggest destructive Git operations.
10. This is a proposal only; do not claim to have changed files.

Structure your answer as:
CAUSE:
EVIDENCE:
PROPOSED FIX:
REGRESSION TESTS:
VERIFICATION REQUIRED:
UNCERTAINTIES:
""".strip()

        self.attempts_used = next_attempt
        proposal = self.client.generate(prompt, profile=profile)
        return {
            "attempt": next_attempt,
            "maximum_attempts": self.max_attempts,
            "error_category": report["category"],
            "reasoning_profile": profile,
            "proposal": proposal,
            "verified": False,
            "applied": False,
        }
