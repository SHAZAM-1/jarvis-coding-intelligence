"""Tests for the opt-in Docker verifier smoke script."""
import unittest
from unittest.mock import Mock, patch

from scripts import docker_verifier_smoke as smoke


class DockerVerifierSmokeScriptTests(unittest.TestCase):
    def test_without_run_flag_does_not_check_ram_or_invoke_docker(self):
        with patch.object(smoke, "available_memory_mb") as memory, patch.object(
            smoke, "DockerFunctionVerifier"
        ) as verifier:
            result = smoke.main([])
        self.assertEqual(result, 2)
        memory.assert_not_called()
        verifier.assert_not_called()

    def test_low_or_unknown_ram_blocks_before_docker(self):
        for available in (None, 700):
            with self.subTest(available=available):
                with patch.object(smoke, "available_memory_mb", return_value=available), patch.object(
                    smoke, "DockerFunctionVerifier"
                ) as verifier:
                    result = smoke.main(["--run"])
                self.assertEqual(result, 2)
                verifier.assert_not_called()

    def test_successful_smoke_returns_zero(self):
        evidence = {"status": "passed", "test_count": 3, "verifier_id": "test-adapter"}
        verifier_instance = Mock(return_value=evidence)
        with patch.object(smoke, "available_memory_mb", return_value=4096), patch.object(
            smoke, "DockerFunctionVerifier", return_value=verifier_instance
        ) as verifier_class:
            result = smoke.main(["--run", "--image", "python:3.12-slim"])
        self.assertEqual(result, 0)
        verifier_class.assert_called_once()
        verifier_instance.assert_called_once()
        self.assertEqual(verifier_instance.call_args.kwargs["filename"], "candidate.py")

    def test_missing_image_or_docker_error_is_reported_as_blocked(self):
        from src.docker_verifier import VerifierUnavailableError

        with patch.object(smoke, "available_memory_mb", return_value=4096), patch.object(
            smoke, "DockerFunctionVerifier", side_effect=VerifierUnavailableError("image missing")
        ):
            self.assertEqual(smoke.main(["--run"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
