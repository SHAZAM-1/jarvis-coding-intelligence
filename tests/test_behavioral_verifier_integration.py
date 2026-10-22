"""Opt-in real-Docker integration checks.

These tests skip without explicit opt-in and a preloaded digest-pinned image.
They never pull an image automatically. Do not set the opt-in flag in generic CI.
"""

import os
import subprocess
import unittest

from src.behavioral_verifier import (
    BehavioralVerificationError,
    BehavioralVerifier,
    VerificationUnavailableError,
)
from src.resource_guard import available_memory_mb
from src.behavioral_verifier import MIN_FREE_RAM_MB


_RUN_SANDBOX_TESTS = os.environ.get("JARVIS_RUN_DOCKER_SANDBOX_TESTS") == "1"


@unittest.skipUnless(
    _RUN_SANDBOX_TESTS,
    "set JARVIS_RUN_DOCKER_SANDBOX_TESTS=1 to opt in to real Docker tests",
)
class DockerBehavioralVerifierIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = os.environ.get("JARVIS_SANDBOX_IMAGE", "")
        if not image:
            raise unittest.SkipTest(
                "JARVIS_SANDBOX_IMAGE must name an already-present digest-pinned image."
            )
        free_ram = available_memory_mb()
        if free_ram is None or free_ram < MIN_FREE_RAM_MB:
            raise unittest.SkipTest(
                f"requires at least {MIN_FREE_RAM_MB} MiB free RAM."
            )
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise unittest.SkipTest("Docker client/daemon is unavailable.")
        if result.returncode != 0:
            raise unittest.SkipTest(
                "The pinned image is not present locally; tests never pull images."
            )
        try:
            cls.verifier = BehavioralVerifier(
                image,
                timeout_seconds=4,
                resource_probe=available_memory_mb,
            )
        except ValueError as exc:
            raise unittest.SkipTest(f"invalid local image configuration: {exc}") from exc

    def verify_or_skip(self, source, entrypoint, cases, verifier=None):
        selected = verifier or self.verifier
        try:
            return selected.verify(
                source, entrypoint, cases, allow_execution=True
            )
        except VerificationUnavailableError as exc:
            self.skipTest(f"Sandbox prerequisites became unavailable: {exc}")

    def test_happy_path_returns_receipt_for_all_cases(self):
        result = self.verify_or_skip(
            "def add(a, b):\n    return a + b\n",
            "add",
            [
                {"args": [1, 2], "kwargs": {}, "expected": 3},
                {"args": [2, 5], "kwargs": {}, "expected": 7},
            ],
        )
        self.assertEqual(result.status, "verified")
        self.assertTrue(result.receipt.success)
        self.assertEqual(result.receipt.passed_count, 2)

    def test_wrong_candidate_output_is_not_verified(self):
        result = self.verify_or_skip(
            "def add(a, b):\n    return a - b\n",
            "add",
            [{"args": [1, 2], "kwargs": {}, "expected": 3}],
        )
        self.assertEqual(result.status, "behavioral_failed")
        self.assertFalse(result.receipt.success)
        self.assertEqual(result.receipt.failed_count, 1)

    def test_network_access_is_disabled_inside_container(self):
        source = (
            "import socket\n"
            "def network_is_blocked():\n"
            "    try:\n"
            "        socket.create_connection(('192.0.2.1', 80), timeout=0.5)\n"
            "    except OSError:\n"
            "        return True\n"
            "    return False\n"
        )
        result = self.verify_or_skip(
            source,
            "network_is_blocked",
            [{"args": [], "kwargs": {}, "expected": True}],
        )
        self.assertEqual(result.status, "verified")

    def test_infinite_loop_times_out_without_a_verified_receipt(self):
        verifier = BehavioralVerifier(
            self.verifier.image_digest,
            timeout_seconds=1,
            resource_probe=available_memory_mb,
        )
        with self.assertRaisesRegex(BehavioralVerificationError, "timed out"):
            verifier.verify(
                "def spin():\n    while True:\n        pass\n",
                "spin",
                [{"args": [], "kwargs": {}, "expected": None}],
                allow_execution=True,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
