"""Non-executing syntax verification for proposed Python code."""

import ast
import hashlib
import os


MAX_SOURCE_BYTES = 262144


class VerificationInputError(ValueError):
    """Raised when proposed source violates input restrictions."""


def verify_python_source(source, filename="candidate.py"):
    """Parse proposed Python source without executing it."""

    if not isinstance(source, str):
        raise VerificationInputError("Source must be a string.")
    if not isinstance(filename, str):
        raise VerificationInputError("Filename must be a string.")
    if (
        not filename
        or filename in (".", "..")
        or os.path.basename(filename) != filename
        or "/" in filename
        or "\\" in filename
        or not filename.endswith(".py")
    ):
        raise VerificationInputError(
            "Provide a simple Python filename, such as candidate.py."
        )

    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VerificationInputError(
            "Source must be encodable as UTF-8."
        ) from exc
    if len(encoded) > MAX_SOURCE_BYTES:
        raise VerificationInputError(
            f"Source exceeds the {MAX_SOURCE_BYTES}-byte limit."
        )

    digest = hashlib.sha256(encoded).hexdigest()
    try:
        ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return {
            "status": "syntax_invalid",
            "syntax_valid": False,
            "verified_fix": False,
            "filename": filename,
            "sha256": digest,
            "error": {
                "type": type(exc).__name__,
                "message": exc.msg,
                "line": exc.lineno,
                "column": exc.offset,
            },
            "checks_performed": ["python_syntax"],
            "checks_not_performed": [
                "runtime_execution", "unit_tests", "regression_tests",
                "security_review", "behavioral_correctness",
            ],
        }

    return {
        "status": "syntax_valid",
        "syntax_valid": True,
        "verified_fix": False,
        "filename": filename,
        "sha256": digest,
        "error": None,
        "checks_performed": ["python_syntax"],
        "checks_not_performed": [
            "runtime_execution", "unit_tests", "regression_tests",
            "security_review", "behavioral_correctness",
        ],
    }
