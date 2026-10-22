"""Opt-in smoke test for the Docker behavioral verifier.

This tests a fixed, harmless add() function; it does not call Ollama or use
model-generated code. Docker images are never pulled automatically.
"""
import argparse
import hashlib

from src.docker_verifier import DockerFunctionVerifier, DockerVerifierError
from src.resource_guard import available_memory_mb

MIN_FREE_RAM_MB = 1536
SOURCE = "def add(a, b):\n    return a + b\n"
TEST_CASES = [
    {"args": [1, 2], "kwargs": {}, "expected": 3},
    {"args": [-2, 5], "kwargs": {}, "expected": 3},
    {"args": [0, 0], "kwargs": {}, "expected": 0},
]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a fixed add() smoke test inside an already-installed Docker image."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="explicitly allow the Docker image check and isolated container run",
    )
    parser.add_argument(
        "--image",
        default="python:3.12-slim",
        help="Docker image that must already exist locally (default: python:3.12-slim)",
    )
    args = parser.parse_args(argv)
    if not args.run:
        parser.print_help()
        print("\nNo Docker command was run. Add --run only when ready for the smoke test.")
        return 2

    free_ram_mb = available_memory_mb()
    if free_ram_mb is None or free_ram_mb < MIN_FREE_RAM_MB:
        print(
            "BLOCKED: available RAM is unknown or below "
            f"{MIN_FREE_RAM_MB} MiB; no Docker command was run."
        )
        return 2

    try:
        verifier = DockerFunctionVerifier(
            function_name="add",
            test_cases=TEST_CASES,
            image=args.image,
            timeout_seconds=15,
        )
        result = verifier(
            SOURCE,
            filename="candidate.py",
            source_sha256=hashlib.sha256(SOURCE.encode("utf-8")).hexdigest(),
        )
    except (DockerVerifierError, ValueError) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        return 2

    print(
        "Docker verifier smoke result: "
        f"{result['status']} ({result['test_count']} fixed cases; "
        f"verifier={result['verifier_id']})"
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
