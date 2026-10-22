"""Opt-in Docker-isolated behavioral checks for JSON-callable Python functions.

The adapter never pulls images and never executes candidate code on the host.
It supports a narrow contract: a candidate module exposes one function that
accepts JSON-compatible args/kwargs and returns a JSON-compatible value. Trusted
expected values stay in the container-side runner, not the candidate process.
"""
import hashlib
import json
import keyword
import math
import os
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone

from src.verification_runner import MAX_SOURCE_BYTES, verify_python_source

_MAX_CASES = 50
_MAX_PAYLOAD_BYTES = 65536
_MAX_OUTPUT_BYTES = 16384
_CHILD_TIMEOUT_SECONDS = 2.0
_RESULT_PREFIX = "JARVIS_VERIFIER_RESULT="


class DockerVerifierError(RuntimeError):
    """Base error for the optional Docker behavioral verifier."""


class VerifierUnavailableError(DockerVerifierError):
    """Docker or the configured preinstalled image is unavailable."""


class VerifierExecutionError(DockerVerifierError):
    """The sandbox timed out, exceeded limits, or returned invalid evidence."""


def _run_bounded(command, input_text=None, timeout_seconds=20, output_limit=_MAX_OUTPUT_BYTES):
    """Run a process with bounded output, timeout, and deterministic pipe cleanup."""
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
    except OSError as exc:
        raise VerifierUnavailableError("Could not start the configured Docker command.") from exc

    output = bytearray()
    overflow = threading.Event()

    def read_output():
        while True:
            try:
                chunk = process.stdout.read(4096)
            except (OSError, ValueError):
                # The owner closes the pipe after bounded joins during cleanup.
                return
            if not chunk:
                return
            room = output_limit - len(output)
            if room > 0:
                output.extend(chunk[:room])
            if len(chunk) > room:
                overflow.set()
                try:
                    process.kill()
                except OSError:
                    pass
                return

    def write_input():
        if input_text is None:
            return
        try:
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            return

    reader = threading.Thread(target=read_output, daemon=True)
    writer = None
    timed_out = False
    try:
        reader.start()
        if input_text is not None:
            writer = threading.Thread(target=write_input, daemon=True)
            writer.start()

        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                process.kill()
            except OSError:
                pass
            process.wait()

        reader.join(timeout=2)
        if writer is not None:
            writer.join(timeout=2)
    finally:
        # Do not leave a subprocess running if an unexpected wait/thread error
        # occurs. Close parent-side pipes on every exit path to avoid ResourceWarning
        # and release OS handles deterministically.
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
            process.wait()

        for pipe in (process.stdin, process.stdout):
            if pipe is not None and not pipe.closed:
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass

    return (
        process.returncode,
        output.decode("utf-8", errors="replace"),
        timed_out,
        overflow.is_set(),
    )

_RUNNER_SOURCE = r'''import json
import os
import subprocess
import sys

RESULT_PREFIX = "JARVIS_VERIFIER_RESULT="
CHILD_RUNNER = r"""
import contextlib
import importlib.util
import io
import json
import sys

request = json.loads(sys.stdin.read())
output_stream = sys.stdout
json_dump = json.dumps
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        sys.path.insert(0, "/workspace")
        spec = importlib.util.spec_from_file_location("candidate_module", "/workspace/candidate.py")
        if spec is None or spec.loader is None:
            raise ImportError("candidate module could not be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        function = getattr(module, request["function_name"])
        value = function(*request["args"], **request["kwargs"])
    response = {"ok": True, "result": value}
except BaseException as exc:
    response = {"ok": False, "error_type": type(exc).__name__}
output_stream.write(json_dump(response, allow_nan=False) + "\n")
"""

def main():
    payload = json.load(sys.stdin)
    passed = 0
    failures = []
    for index, case in enumerate(payload["cases"]):
        request = {
            "function_name": payload["function_name"],
            "args": case["args"],
            "kwargs": case["kwargs"],
        }
        try:
            child = subprocess.run(
                [sys.executable, "-I", "-B", "-c", CHILD_RUNNER],
                input=json.dumps(request, allow_nan=False),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2.0,
                cwd="/workspace",
                env={"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                     "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )
        except subprocess.TimeoutExpired:
            failures.append({"case": index, "reason": "timeout"})
            continue
        except OSError:
            failures.append({"case": index, "reason": "process_error"})
            continue

        lines = child.stdout.splitlines()
        try:
            response = json.loads(lines[-1]) if lines else {}
        except (ValueError, TypeError):
            response = {}
        if child.returncode != 0 or response.get("ok") is not True:
            failures.append({"case": index, "reason": "candidate_error"})
        else:
            try:
                actual = json.dumps(response.get("result"), sort_keys=True, allow_nan=False)
                expected = json.dumps(case["expected"], sort_keys=True, allow_nan=False)
            except (TypeError, ValueError):
                actual = None
                expected = "not-json"
            if actual != expected:
                failures.append({"case": index, "reason": "unexpected_result"})
            else:
                passed += 1

    summary = {
        "status": "passed" if passed == len(payload["cases"]) else "failed",
        "test_count": len(payload["cases"]),
        "passed_count": passed,
        "failed_count": len(failures),
        "failures": failures[:20],
    }
    print(RESULT_PREFIX + json.dumps(summary, separators=(",", ":"), allow_nan=False))
    raise SystemExit(0 if summary["status"] == "passed" else 1)

if __name__ == "__main__":
    main()
'''


class DockerFunctionVerifier:
    """Verify JSON-callable functions in an opt-in, network-disabled container.

    The Docker image must already exist locally. No image pulls are performed.
    This is defense in depth, not a guarantee against container-runtime/kernel
    vulnerabilities. Test cases are intentionally limited to JSON values.
    """

    def __init__(
        self,
        function_name,
        test_cases,
        image="python:3.12-slim",
        timeout_seconds=20,
        docker_executable="docker",
    ):
        if (
            not isinstance(function_name, str)
            or not function_name.isidentifier()
            or keyword.iskeyword(function_name)
        ):
            raise ValueError("function_name must be a non-keyword Python identifier.")
        if not isinstance(image, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,127}", image
        ):
            raise ValueError("image must be a simple Docker image reference.")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
        ):
            raise ValueError("timeout_seconds must be finite and between 1 and 120.")
        try:
            timeout_is_finite = math.isfinite(timeout_seconds)
        except (OverflowError, TypeError):
            timeout_is_finite = False
        if not timeout_is_finite or not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be finite and between 1 and 120.")
        if not isinstance(docker_executable, str) or not docker_executable.strip():
            raise ValueError("docker_executable must be a non-empty command.")

        self.function_name = function_name
        self.image = image
        self.timeout_seconds = float(timeout_seconds)
        self.docker_executable = docker_executable

        if not isinstance(test_cases, list) or not 1 <= len(test_cases) <= _MAX_CASES:
            raise ValueError(f"test_cases must contain between 1 and {_MAX_CASES} cases.")
        for case in test_cases:
            if not isinstance(case, dict) or set(case) != {"args", "kwargs", "expected"}:
                raise ValueError("Each case must contain exactly args, kwargs, and expected.")
            if not isinstance(case["args"], list) or not isinstance(case["kwargs"], dict):
                raise ValueError("Each case requires a list of args and dictionary of kwargs.")
        try:
            encoded = json.dumps(
                {"function_name": function_name, "cases": test_cases},
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("Test cases must contain only finite JSON-compatible values.") from exc
        if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
            raise ValueError("Combined test-case payload exceeds 64 KiB.")
        self.test_cases = json.loads(encoded)
        identity = json.dumps(
            {"image": image, "suite": encoded}, sort_keys=True, separators=(",", ":")
        )
        suite_digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        self.verifier_id = f"docker-json-function-v1:{suite_digest}"

    def __call__(self, source, filename="candidate.py", source_sha256=None):
        """Run configured cases and return coordinator-compatible evidence."""
        if not isinstance(source, str):
            raise ValueError("source must be a string.")
        syntax = verify_python_source(source, filename="candidate.py")
        if not syntax["syntax_valid"]:
            raise ValueError("Candidate must pass syntax validation before behavioral tests.")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if source_sha256 != digest:
            raise ValueError("source_sha256 does not match the candidate source.")
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("Candidate source exceeds the configured byte limit.")

        inspect_result = _run_bounded(
            [self.docker_executable, "image", "inspect", self.image],
            timeout_seconds=3,
            output_limit=4096,
        )
        inspect_code, _, inspect_timeout, inspect_overflow = inspect_result
        if inspect_timeout or inspect_overflow or inspect_code != 0:
            raise VerifierUnavailableError(
                "Docker or the configured image is unavailable locally; automatic pulls are disabled."
            )

        payload = json.dumps(
            {"function_name": self.function_name, "cases": self.test_cases},
            allow_nan=False,
            separators=(",", ":"),
        )
        with tempfile.TemporaryDirectory(prefix="jarvis-docker-verifier-") as workspace:
            candidate_path = os.path.join(workspace, "candidate.py")
            runner_path = os.path.join(workspace, "runner.py")
            with open(candidate_path, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(source)
            with open(runner_path, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(_RUNNER_SOURCE)

            mount_source = os.path.abspath(workspace).replace("\\", "/")
            if "," in mount_source:
                raise VerifierExecutionError(
                    "Temporary workspace path contains a Docker mount delimiter."
                )
            container_name = f"jarvis-verifier-{uuid.uuid4().hex[:20]}"
            command = [
                self.docker_executable, "run", "--rm", "--pull=never",
                "--name", container_name,
                "--network=none", "--read-only", "--memory=256m", "--cpus=0.5",
                "--pids-limit=32", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--user=0:0",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                "--env", "PYTHONDONTWRITEBYTECODE=1",
                "--mount", f"type=bind,source={mount_source},target=/workspace,readonly",
                self.image, "python", "-I", "-B", "/workspace/runner.py",
            ]
            exit_code, output, timed_out, overflow = _run_bounded(
                command, input_text=payload, timeout_seconds=self.timeout_seconds,
                output_limit=_MAX_OUTPUT_BYTES,
            )
            if timed_out or overflow:
                # Killing the Docker CLI alone may leave the daemon-managed
                # container running. Best-effort cleanup targets this unique
                # container name and is bounded independently.
                for cleanup_args in (["kill", container_name], ["rm", "--force", container_name]):
                    try:
                        _run_bounded(
                            [self.docker_executable, *cleanup_args],
                            timeout_seconds=3,
                            output_limit=4096,
                        )
                    except DockerVerifierError:
                        # Preserve the original timeout/output-limit failure.
                        pass
        if timed_out:
            raise VerifierExecutionError("Docker behavioral verification timed out.")
        if overflow:
            raise VerifierExecutionError("Docker behavioral verification exceeded output limits.")

        summary = None
        for line in reversed(output.splitlines()):
            if line.startswith(_RESULT_PREFIX):
                try:
                    summary = json.loads(line[len(_RESULT_PREFIX):])
                except (ValueError, TypeError):
                    summary = None
                break
        if not isinstance(summary, dict):
            raise VerifierExecutionError("Docker runner returned no valid result summary.")

        test_count = summary.get("test_count")
        passed_count = summary.get("passed_count")
        failed_count = summary.get("failed_count")
        passed = (
            exit_code == 0
            and summary.get("status") == "passed"
            and isinstance(test_count, int)
            and not isinstance(test_count, bool)
            and test_count == len(self.test_cases)
            and isinstance(passed_count, int)
            and not isinstance(passed_count, bool)
            and passed_count == test_count
            and isinstance(failed_count, int)
            and not isinstance(failed_count, bool)
            and failed_count == 0
        )
        return {
            "status": "passed" if passed else "failed",
            "source_sha256": digest,
            "verifier_id": self.verifier_id,
            "run_id": uuid.uuid4().hex,
            "checks_performed": ["behavioral_tests", "docker_isolation"],
            "commands": [
                f"docker run --pull=never --network=none --read-only {self.image} "
                "python -I -B /workspace/runner.py"
            ],
            "exit_code": 0 if passed else (exit_code if exit_code else 1),
            "test_count": len(self.test_cases),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
        }
