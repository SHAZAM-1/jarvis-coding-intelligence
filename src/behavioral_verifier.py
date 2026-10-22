"""Opt-in Docker-isolated behavioral checks for JSON-compatible Python callables.

Generated code is never executed directly on the host. The verifier fails closed
when Docker, a pinned local image, RAM headroom, or required controls are absent.
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.resource_guard import available_memory_mb
from src.verification_runner import MAX_SOURCE_BYTES, verify_python_source


MAX_CASES = 20
MAX_CASE_BYTES = 4096
MAX_PROTOCOL_BYTES = 65536
MAX_OUTPUT_BYTES = 65536
MAX_TIMEOUT_SECONDS = 30
MIN_FREE_RAM_MB = 1536
SANDBOX_POLICY = "docker-json-callable-v1"
_IMAGE_DIGEST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_-]*@sha256:[0-9a-f]{64}$")
_ENTRYPOINT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_RECEIPT_ISSUER = object()


class VerificationUnavailableError(RuntimeError):
    """Raised when required sandbox prerequisites are unavailable."""


class BehavioralVerificationError(RuntimeError):
    """Raised when the sandbox run cannot produce trustworthy results."""


@dataclass(frozen=True)
class VerificationReceipt:
    """Compact evidence created by the behavioral verifier."""

    source_sha256: str
    manifest_sha256: str
    image_digest: str
    sandbox_policy: str
    case_count: int
    answered_count: int
    passed_count: int
    failed_count: int
    exit_code: int
    elapsed_seconds: float
    timestamp: str
    success: bool
    _issuer: object = field(default=None, repr=False, compare=False)

    def to_dict(self):
        """Return bounded, source-free evidence suitable for the learning ledger."""
        return {
            "source_sha256": self.source_sha256,
            "manifest_sha256": self.manifest_sha256,
            "image_digest": self.image_digest,
            "sandbox_policy": self.sandbox_policy,
            "case_count": self.case_count,
            "answered_count": self.answered_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "exit_code": self.exit_code,
            "elapsed_seconds": self.elapsed_seconds,
            "timestamp": self.timestamp,
            "success": self.success,
        }


@dataclass(frozen=True)
class BehavioralVerificationResult:
    """Outcome for a completed test run; it is not a general correctness proof."""

    status: str
    receipt: VerificationReceipt
    failed_case_indices: tuple


def is_trusted_receipt(receipt):
    """Check that the receipt was issued by this verifier implementation."""
    return (
        isinstance(receipt, VerificationReceipt)
        and receipt._issuer is _RECEIPT_ISSUER
    )


def _canonical_json(value, maximum_bytes):
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Test cases must contain only finite JSON values.") from exc
    if len(encoded) > maximum_bytes:
        raise ValueError("JSON test data exceeds the configured size limit.")
    return encoded


def _validate_cases(cases):
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError(f"cases must contain between 1 and {MAX_CASES} entries.")

    normalized = []
    input_lines = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {"args", "kwargs", "expected"}:
            raise ValueError(
                f"case {index} must contain exactly args, kwargs, and expected."
            )
        args = case["args"]
        kwargs = case["kwargs"]
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            raise ValueError(f"case {index} args must be a list and kwargs a dict.")
        if any(not isinstance(key, str) for key in kwargs):
            raise ValueError(f"case {index} keyword names must be strings.")

        input_data = {"args": args, "kwargs": kwargs}
        input_bytes = _canonical_json(input_data, MAX_CASE_BYTES)
        expected_bytes = _canonical_json(case["expected"], MAX_CASE_BYTES)
        normalized.append({
            "args": json.loads(input_bytes.decode("utf-8")),
            "kwargs": json.loads(input_bytes.decode("utf-8"))["kwargs"],
            "expected": json.loads(expected_bytes.decode("utf-8")),
        })
        input_lines.append(input_bytes + b"\n")

    payload = b"".join(input_lines)
    if len(payload) > MAX_PROTOCOL_BYTES:
        raise ValueError("Combined test inputs exceed the protocol size limit.")
    manifest = _canonical_json(normalized, MAX_PROTOCOL_BYTES)
    return normalized, payload, hashlib.sha256(manifest).hexdigest()


_WORKER_SOURCE = r'''
import importlib.util
import json
import sys

_json_loads = json.loads
_json_dumps = json.dumps
_stdin = sys.stdin
_stdout = sys.stdout

sys.path.insert(0, "/workspace")
entrypoint = sys.argv[1]
spec = importlib.util.spec_from_file_location("candidate", "/workspace/candidate.py")
if spec is None or spec.loader is None:
    raise RuntimeError("candidate module could not be loaded")
module = importlib.util.module_from_spec(spec)
sys.modules["candidate"] = module
spec.loader.exec_module(module)
function = getattr(module, entrypoint)
if not callable(function):
    raise TypeError("entry point is not callable")

for line in _stdin:
    request = _json_loads(line)
    if not isinstance(request, dict) or set(request) != {"args", "kwargs"}:
        raise ValueError("invalid request protocol")
    try:
        value = function(*request["args"], **request["kwargs"])
        encoded = _json_dumps(
            {"ok": True, "value": value},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        )
    except Exception as exc:
        encoded = _json_dumps(
            {"ok": False, "error": type(exc).__name__},
            separators=(",", ":"),
        )
    _stdout.write(encoded + "\n")
    _stdout.flush()
'''


class BehavioralVerifier:
    """Run opt-in callable tests inside a restricted, preloaded Docker image."""

    def __init__(
        self,
        image_digest,
        docker_executable="docker",
        timeout_seconds=10,
        resource_probe=available_memory_mb,
        run_func=subprocess.run,
        popen_factory=subprocess.Popen,
    ):
        if not isinstance(image_digest, str) or not _IMAGE_DIGEST.fullmatch(image_digest):
            raise ValueError("image_digest must include an immutable @sha256 digest.")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"timeout_seconds must be greater than 0 and at most "
                f"{MAX_TIMEOUT_SECONDS}."
            )
        if not isinstance(docker_executable, str) or not docker_executable.strip():
            raise ValueError("docker_executable must be a non-empty string.")
        self.image_digest = image_digest
        self.docker_executable = docker_executable
        self.timeout_seconds = float(timeout_seconds)
        self.resource_probe = resource_probe
        self.run_func = run_func
        self.popen_factory = popen_factory

    def verify(self, source, entrypoint, cases, *, allow_execution=False):
        """Verify declared input/output cases; execution is opt-in and fail-closed."""
        if allow_execution is not True:
            raise VerificationUnavailableError(
                "Behavioral execution is disabled; explicitly opt in to enable it."
            )
        if not isinstance(source, str):
            raise ValueError("source must be a string.")
        if len(source.encode("utf-8")) > min(MAX_SOURCE_BYTES, 65536):
            raise ValueError("candidate source exceeds the behavioral-verification limit.")
        if not isinstance(entrypoint, str) or not _ENTRYPOINT.fullmatch(entrypoint):
            raise ValueError("entrypoint must be a simple Python identifier.")

        syntax = verify_python_source(source)
        if not syntax["syntax_valid"]:
            raise ValueError("candidate source must pass syntax verification first.")
        normalized_cases, input_payload, manifest_hash = _validate_cases(cases)

        free_mb = self.resource_probe()
        if free_mb is None or free_mb < MIN_FREE_RAM_MB:
            raise VerificationUnavailableError(
                f"Sandbox execution requires at least {MIN_FREE_RAM_MB} MiB free RAM."
            )
        self._require_local_image()

        started = time.monotonic()
        container_name = "jarvis-verify-" + uuid.uuid4().hex[:20]
        try:
            with tempfile.TemporaryDirectory(prefix="jarvis-verifier-") as temp:
                workspace = Path(temp).resolve()
                if "," in str(workspace):
                    raise VerificationUnavailableError(
                        "Temporary workspace paths containing commas are unsupported."
                    )
                (workspace / "candidate.py").write_text(source, encoding="utf-8")
                (workspace / "worker.py").write_text(
                    _WORKER_SOURCE, encoding="utf-8"
                )
                try:
                    os.chmod(workspace, 0o755)
                    os.chmod(workspace / "candidate.py", 0o644)
                    os.chmod(workspace / "worker.py", 0o644)
                except OSError:
                    # The container still mounts read-only; unsupported host
                    # permission semantics are surfaced by the run and fail closed.
                    pass

                command = self._container_command(
                    container_name, workspace, entrypoint
                )
                stdout, stderr, exit_code = self._run_bounded(
                    command, input_payload, container_name
                )
        except (OSError, subprocess.SubprocessError) as exc:
            self._cleanup_container(container_name)
            raise BehavioralVerificationError(
                "Sandbox process failed; no verification receipt was issued."
            ) from exc

        elapsed = time.monotonic() - started
        if exit_code != 0:
            raise BehavioralVerificationError(
                "Sandbox exited unsuccessfully; no verification receipt was issued."
            )
        responses = self._parse_responses(stdout, len(normalized_cases))
        failed = []
        answered = 0
        passed = 0
        for index, (response, case) in enumerate(zip(responses, normalized_cases)):
            answered += 1
            if response.get("ok") is not True:
                failed.append(index)
                continue
            try:
                actual = _canonical_json(response.get("value"), MAX_CASE_BYTES)
                expected = _canonical_json(case["expected"], MAX_CASE_BYTES)
            except ValueError:
                failed.append(index)
                continue
            if actual == expected:
                passed += 1
            else:
                failed.append(index)

        success = answered == len(normalized_cases) and passed == len(normalized_cases)
        receipt = VerificationReceipt(
            source_sha256=syntax["sha256"],
            manifest_sha256=manifest_hash,
            image_digest=self.image_digest,
            sandbox_policy=SANDBOX_POLICY,
            case_count=len(normalized_cases),
            answered_count=answered,
            passed_count=passed,
            failed_count=len(failed),
            exit_code=exit_code,
            elapsed_seconds=round(elapsed, 3),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            success=success,
            _issuer=_RECEIPT_ISSUER,
        )
        return BehavioralVerificationResult(
            status="verified" if success else "behavioral_failed",
            receipt=receipt,
            failed_case_indices=tuple(failed),
        )

    def _require_local_image(self):
        try:
            result = self.run_func(
                [self.docker_executable, "image", "inspect", self.image_digest],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise VerificationUnavailableError(
                "Docker is unavailable; host execution fallback is forbidden."
            ) from exc
        if result.returncode != 0:
            raise VerificationUnavailableError(
                "Approved sandbox image is not available locally; automatic pulls are disabled."
            )

    def _container_command(self, container_name, workspace, entrypoint):
        mount = f"type=bind,src={workspace},dst=/workspace,readonly"
        return [
            self.docker_executable, "run", "--rm", "--pull=never",
            "--name", container_name,
            "--network=none", "--read-only",
            "--memory=256m", "--memory-swap=256m", "--cpus=0.5",
            "--pids-limit=32", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--user=65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--mount", mount, "--workdir", "/workspace",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            self.image_digest, "python", "-I", "-S",
            "/workspace/worker.py", entrypoint,
        ]

    def _run_bounded(self, command, input_payload, container_name):
        try:
            process = self.popen_factory(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise BehavioralVerificationError(
                "Could not start the Docker client."
            ) from exc

        output = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()

        def drain(stream, key):
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                if len(output[key]) + len(chunk) > MAX_OUTPUT_BYTES:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return
                output[key].extend(chunk)

        readers = [
            threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()

        def write_input():
            try:
                process.stdin.write(input_payload)
                process.stdin.flush()
                process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        writer = threading.Thread(target=write_input, daemon=True)
        writer.start()
        try:
            exit_code = process.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            self._cleanup_container(container_name)
            raise BehavioralVerificationError(
                "Sandbox timed out; container cleanup was requested."
            ) from exc
        finally:
            for reader in readers:
                reader.join(timeout=1)
            writer.join(timeout=1)

        if overflow.is_set():
            self._cleanup_container(container_name)
            raise BehavioralVerificationError(
                "Sandbox output exceeded the configured limit."
            )
        return bytes(output["stdout"]), bytes(output["stderr"]), exit_code

    @staticmethod
    def _parse_responses(stdout, expected_count):
        try:
            text = stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BehavioralVerificationError(
                "Sandbox emitted invalid UTF-8; verification failed closed."
            ) from exc
        lines = text.splitlines()
        if len(lines) != expected_count:
            raise BehavioralVerificationError(
                "Sandbox response count did not match submitted test cases."
            )
        responses = []
        for line in lines:
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BehavioralVerificationError(
                    "Sandbox emitted malformed protocol output."
                ) from exc
            if not isinstance(response, dict) or response.get("ok") not in (True, False):
                raise BehavioralVerificationError(
                    "Sandbox response did not match the worker protocol."
                )
            if response.get("ok") is True and set(response) != {"ok", "value"}:
                raise BehavioralVerificationError(
                    "Successful sandbox response contained unexpected fields."
                )
            if response.get("ok") is False and set(response) != {"ok", "error"}:
                raise BehavioralVerificationError(
                    "Failed sandbox response contained unexpected fields."
                )
            responses.append(response)
        return responses

    def _cleanup_container(self, container_name):
        try:
            self.run_func(
                [self.docker_executable, "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            # Cleanup failure is reported by the primary failure path; never
            # fall back to running the candidate outside the container.
            return
