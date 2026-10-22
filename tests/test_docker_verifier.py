"""Tests for DockerFunctionVerifier without requiring Docker or an image."""
import ast
import hashlib
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.docker_verifier import (
    DockerFunctionVerifier,
    VerifierExecutionError,
    VerifierUnavailableError,
    _run_bounded,
    _RUNNER_SOURCE,
)

SOURCE = "def add(a, b):\n    return a + b\n"
DIGEST = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()


def _summary(status="passed", test_count=2, passed_count=2, failed_count=0):
    return "JARVIS_VERIFIER_RESULT=" + json.dumps({
        "status": status,
        "test_count": test_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "failures": [],
    })


class DockerFunctionVerifierTests(unittest.TestCase):
    def setUp(self):
        self.verifier = DockerFunctionVerifier(
            "add",
            [
                {"args": [1, 2], "kwargs": {}, "expected": 3},
                {"args": [-2, 5], "kwargs": {}, "expected": 3},
            ],
            image="python:3.12-slim",
        )

    def test_generated_parent_and_child_runner_sources_parse(self):
        parent_tree = ast.parse(_RUNNER_SOURCE)
        assignment = next(
            node for node in ast.walk(parent_tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "CHILD_RUNNER"
                for target in node.targets
            )
        )
        child_source = ast.literal_eval(assignment.value)
        ast.parse(child_source)

    def test_configuration_rejects_invalid_function_and_image(self):
        with self.assertRaises(ValueError):
            DockerFunctionVerifier("not-valid!", [{"args": [], "kwargs": {}, "expected": 1}])
        with self.assertRaises(ValueError):
            DockerFunctionVerifier("add", [{"args": [], "kwargs": {}, "expected": 1}], image="bad image")

    def test_configuration_rejects_invalid_timeout(self):
        for value in (0, 121, True, float("nan"), float("inf"), 10**1000):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    DockerFunctionVerifier(
                        "add", [{"args": [], "kwargs": {}, "expected": 1}],
                        timeout_seconds=value,
                    )

    def test_configuration_rejects_empty_or_oversized_case_lists(self):
        with self.assertRaises(ValueError):
            DockerFunctionVerifier("add", [])
        with self.assertRaises(ValueError):
            DockerFunctionVerifier(
                "add", [{"args": [], "kwargs": {}, "expected": 0}] * 51
            )

    def test_configuration_rejects_non_json_values(self):
        with self.assertRaises(ValueError):
            DockerFunctionVerifier(
                "add", [{"args": [float("nan")], "kwargs": {}, "expected": 0}]
            )

    def test_source_hash_mismatch_fails_before_docker(self):
        with patch("src.docker_verifier._run_bounded") as run:
            with self.assertRaises(ValueError):
                self.verifier(SOURCE, source_sha256="0" * 64)
            run.assert_not_called()

    def test_missing_local_image_never_attempts_a_pull(self):
        with patch(
            "src.docker_verifier._run_bounded",
            return_value=(1, "not found", False, False),
        ) as run:
            with self.assertRaises(VerifierUnavailableError):
                self.verifier(SOURCE, source_sha256=DIGEST)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][1:3], ["image", "inspect"])

    def test_success_returns_source_bound_behavioral_evidence(self):
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[
                (0, "", False, False),
                (0, _summary(), False, False),
            ],
        ) as run:
            evidence = self.verifier(SOURCE, source_sha256=DIGEST)
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["source_sha256"], DIGEST)
        self.assertEqual(evidence["verifier_id"], self.verifier.verifier_id)
        self.assertEqual(evidence["test_count"], 2)
        self.assertEqual(evidence["exit_code"], 0)
        self.assertIn("behavioral_tests", evidence["checks_performed"])
        command = run.call_args_list[1].args[0]
        for required in (
            "--pull=never", "--network=none", "--read-only", "--memory=256m",
            "--pids-limit=32", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        ):
            self.assertIn(required, command)
        self.assertIn("python", command)
        self.assertIn("-I", command)
        self.assertIn("-B", command)

    def test_malformed_success_summary_never_passes(self):
        one_case = DockerFunctionVerifier(
            "add", [{"args": [1, 2], "kwargs": {}, "expected": 3}]
        )
        malformed = "JARVIS_VERIFIER_RESULT=" + json.dumps({
            "status": "passed", "test_count": True,
            "passed_count": True, "failed_count": False, "failures": [],
        })
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[(0, "", False, False), (0, malformed, False, False)],
        ):
            evidence = one_case(SOURCE, source_sha256=DIGEST)
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["exit_code"], 1)

    def test_failed_behavioral_case_returns_failed_evidence(self):
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[
                (0, "", False, False),
                (1, _summary("failed", 2, 1, 1), False, False),
            ],
        ):
            evidence = self.verifier(SOURCE, source_sha256=DIGEST)
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["exit_code"], 1)

    def test_timeout_and_output_overflow_never_pass(self):
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[(0, "", False, False), (0, "", True, False)],
        ):
            with self.assertRaises(VerifierExecutionError):
                self.verifier(SOURCE, source_sha256=DIGEST)
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[(0, "", False, False), (0, "", False, True)],
        ):
            with self.assertRaises(VerifierExecutionError):
                self.verifier(SOURCE, source_sha256=DIGEST)

    def test_missing_result_marker_never_passes(self):
        with patch(
            "src.docker_verifier._run_bounded",
            side_effect=[(0, "", False, False), (0, "unexpected output", False, False)],
        ):
            with self.assertRaises(VerifierExecutionError):
                self.verifier(SOURCE, source_sha256=DIGEST)

    def test_bounded_process_captures_small_output_and_input(self):
        code = "import sys; print(sys.stdin.read())"
        result = _run_bounded([sys.executable, "-c", code], "safe-input", 3, 100)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1].strip(), "safe-input")
        self.assertFalse(result[2])
        self.assertFalse(result[3])

    def test_bounded_process_closes_pipe_handles(self):
        processes = []
        real_popen = subprocess.Popen

        def tracked_popen(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch("src.docker_verifier.subprocess.Popen", side_effect=tracked_popen):
            result = _run_bounded(
                [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
                "safe-input",
                timeout_seconds=3,
                output_limit=100,
            )

        self.assertEqual(result[0], 0)
        self.assertEqual(len(processes), 1)
        self.assertTrue(processes[0].stdin.closed)
        self.assertTrue(processes[0].stdout.closed)

    def test_bounded_process_stops_on_output_overflow(self):
        code = "print('x' * 100000)"
        result = _run_bounded([sys.executable, "-c", code], timeout_seconds=3, output_limit=64)
        self.assertTrue(result[3])
        self.assertLessEqual(len(result[1].encode("utf-8")), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
