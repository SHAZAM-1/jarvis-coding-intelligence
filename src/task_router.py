"""Cheap deterministic task routing for resource-aware reasoning.

This router does not claim to measure intelligence. It selects bounded inference
settings from visible task signals so easy requests stay cheap while harder
debugging/review tasks can receive a larger budget when memory permits.
"""

import re


PROFILES = {"fast", "balanced", "deep"}


def choose_profile(task, failure_output="", available_ram_mb=None):
    """Select fast/balanced/deep from task complexity and available RAM."""
    task = task if isinstance(task, str) else ""
    failure_output = failure_output if isinstance(failure_output, str) else ""
    combined = f"{task}
{failure_output}".lower()

    complexity_signals = (
        "root cause", "race condition", "security", "deadlock",
        "architecture", "refactor", "regression", "multiple files",
        "performance", "memory leak", "concurrency", "traceback",
        "stack trace", "failing tests", "test suite", "review this diff",
    )
    complex = (
        len(combined) > 5000
        or len(re.findall(r"\b(?:class|def|async def)\b", combined)) >= 5
        or sum(signal in combined for signal in complexity_signals) >= 2
    )

    simple_signals = (
        "what does", "explain this line", "one sentence", "format this",
        "rename this variable", "simple example", "translate",
    )
    simple = (
        len(combined) < 1200
        and any(signal in combined for signal in simple_signals)
        and not failure_output.strip()
    )

    profile = "deep" if complex else "fast" if simple else "balanced"

    # Under tight memory, preserve the safety preflight and avoid the deep
    # profile. Unknown RAM does not silently grant the larger profile.
    if available_ram_mb is None:
        return "balanced" if profile == "deep" else profile
    if available_ram_mb < 2048 and profile == "deep":
        return "balanced"
    if available_ram_mb < 1792:
        return "fast" if profile != "deep" else "balanced"
    return profile
