"""Deterministic analysis of common Python and test failures."""

import re


def analyze_error(error_text):
    """Convert error output into a structured diagnostic report."""

    if not isinstance(error_text, str):
        raise TypeError("error_text must be a string")

    text = error_text.strip()

    if not text:
        return {
            "category": "unknown",
            "summary": "No error output was provided.",
            "evidence": "",
            "needs_investigation": True,
        }

    patterns = [
        ("missing_import", r"ModuleNotFoundError|ImportError",
         "A Python module or import could not be resolved."),
        ("syntax_error", r"SyntaxError|IndentationError|TabError",
         "Python could not parse the source code."),
        ("missing_attribute", r"AttributeError",
         "An object does not provide the requested attribute."),
        ("missing_key", r"KeyError",
         "A requested dictionary key was not found."),
        ("type_error", r"TypeError",
         "An operation received an incompatible type or arguments."),
        ("assertion_failure", r"AssertionError|FAILED\s+",
         "An assertion or test expectation failed."),
        ("timeout", r"TimeoutError|timed out|TIMEOUT",
         "An operation exceeded its time limit."),
        ("connection_error",
         r"ConnectionError|ConnectionRefusedError|URLError|Connection refused",
         "A network or service connection failed."),
        ("test_error", r"ERROR:\s+test_|FAILED\s+\(",
         "A test raised an exception or the test suite failed."),
    ]

    for category, pattern, summary in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "category": category,
                "summary": summary,
                "evidence": text[-4000:],
                "needs_investigation": False,
            }

    return {
        "category": "unknown",
        "summary": "The error does not match a recognized pattern.",
        "evidence": text[-4000:],
        "needs_investigation": True,
    }
