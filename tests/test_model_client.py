"""Automated tests for the local Ollama client."""

import json
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from src.model_client import (
    DEFAULT_MODEL, MAX_PROMPT_BYTES, MAX_RESPONSE_BYTES,
    OllamaClient, OllamaClientError,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        raw = json.dumps(self.payload).encode("utf-8")
        return raw if size < 0 else raw[:size]


class OllamaClientTests(unittest.TestCase):
    def setUp(self):
        self.resource_patch = patch(
            "src.model_client.inference_slot",
            return_value=nullcontext(3072),
        )
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)

    def test_default_model_is_selected(self):
        self.assertEqual(OllamaClient().model, DEFAULT_MODEL)

    def test_default_endpoint_is_local(self):
        self.assertEqual(OllamaClient().endpoint, "http://127.0.0.1:11434")

    def test_external_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient(endpoint="http://example.com:11434")

    def test_wrong_port_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient(endpoint="http://127.0.0.1:8080")

    def test_https_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient(endpoint="https://127.0.0.1:11434")

    def test_endpoint_with_credentials_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient(endpoint="http://user:password@127.0.0.1:11434")

    def test_empty_model_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient(model="   ")

    def test_invalid_timeout_is_rejected(self):
        invalid_timeouts = (0, -1, float("nan"), float("inf"), 601, True)
        for timeout in invalid_timeouts:
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    OllamaClient(timeout=timeout)

    def test_timeout_at_upper_bound_is_accepted(self):
        self.assertEqual(OllamaClient(timeout=600).timeout, 600)

    def test_empty_prompt_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient().generate("   ")

    def test_invalid_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient().generate("Test", profile="unlimited")

    @patch("src.model_client.urlopen")
    def test_generate_returns_model_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse({"response": "CODING MODEL ONLINE"})
        result = OllamaClient().generate("Say hello")
        self.assertEqual(result, "CODING MODEL ONLINE")
        request = mock_urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/generate"))
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["prompt"], "Say hello")
        self.assertFalse(body["stream"])
        self.assertEqual(body["keep_alive"], "30s")
        self.assertEqual(body["options"]["num_ctx"], 2048)
        self.assertEqual(body["options"]["num_predict"], 384)
        self.assertEqual(body["options"]["num_thread"], 2)

    @patch("src.model_client.urlopen")
    def test_deep_profile_uses_larger_budget_when_ram_allows(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse({"response": "analysis"})
        OllamaClient().generate("Review complex code", profile="deep")
        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["options"]["num_ctx"], 4096)
        self.assertEqual(body["options"]["num_predict"], 768)

    @patch("src.model_client.inference_slot", return_value=nullcontext(1700))
    @patch("src.model_client.urlopen")
    def test_deep_profile_downgrades_when_ram_is_tight(self, mock_urlopen, _slot):
        mock_urlopen.return_value = FakeResponse({"response": "analysis"})
        OllamaClient().generate("Review complex code", profile="deep")
        request = mock_urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["options"]["num_ctx"], 2048)
        self.assertEqual(body["options"]["num_predict"], 384)

    @patch("src.model_client.urlopen")
    def test_non_object_response_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(["unexpected"])
        with self.assertRaises(OllamaClientError):
            OllamaClient().generate("Test")

    @patch("src.model_client.urlopen")
    def test_missing_response_field_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse({"model": DEFAULT_MODEL})
        with self.assertRaises(OllamaClientError):
            OllamaClient().generate("Test")

    @patch("src.model_client.urlopen")
    def test_invalid_json_is_rejected(self, mock_urlopen):
        class InvalidJsonResponse(FakeResponse):
            def read(self, size=-1):
                return b"{invalid json"
        mock_urlopen.return_value = InvalidJsonResponse({})
        with self.assertRaises(OllamaClientError):
            OllamaClient().generate("Test")

    def test_prompt_size_limit_is_defined(self):
        self.assertEqual(MAX_PROMPT_BYTES, 131072)

    @patch("src.model_client.urlopen")
    def test_oversized_response_is_rejected(self, mock_urlopen):
        class OversizedResponse(FakeResponse):
            def read(self, size=-1):
                return b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_urlopen.return_value = OversizedResponse({})
        with self.assertRaises(OllamaClientError):
            OllamaClient().generate("Test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
