import json
import unittest
from unittest.mock import patch

from src.model_audit import (
    AuditError,
    DEFAULT_ENDPOINT,
    OllamaReadOnlyAudit,
    validate_local_endpoint,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


class ModelAuditTests(unittest.TestCase):
    def test_default_endpoint_is_local(self):
        audit = OllamaReadOnlyAudit()
        self.assertEqual(audit.endpoint, DEFAULT_ENDPOINT)

    def test_accepts_loopback_endpoints(self):
        self.assertEqual(
            validate_local_endpoint("http://127.0.0.1:11434"),
            "http://127.0.0.1:11434",
        )
        self.assertEqual(
            validate_local_endpoint("http://localhost:11434/"),
            "http://localhost:11434",
        )
        self.assertEqual(
            validate_local_endpoint("http://[::1]:11434"),
            "http://[::1]:11434",
        )

    def test_rejects_external_host(self):
        with self.assertRaises(AuditError):
            validate_local_endpoint("http://example.com:11434")

    def test_rejects_https(self):
        with self.assertRaises(AuditError):
            validate_local_endpoint("https://127.0.0.1:11434")

    def test_rejects_wrong_port(self):
        with self.assertRaises(AuditError):
            validate_local_endpoint("http://127.0.0.1:8080")

    def test_rejects_credentials(self):
        with self.assertRaises(AuditError):
            validate_local_endpoint("http://user:pass@127.0.0.1:11434")

    def test_rejects_endpoint_path(self):
        with self.assertRaises(AuditError):
            validate_local_endpoint("http://127.0.0.1:11434/api")

    def test_rejects_invalid_timeout(self):
        for timeout in (0, -1, 61, True, "5"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(AuditError):
                    OllamaReadOnlyAudit(timeout=timeout)

    @patch("src.model_audit.urlopen")
    def test_run_collects_read_only_metadata(self, mock_urlopen):
        mock_urlopen.side_effect = [
            FakeResponse({"version": "test"}),
            FakeResponse({
                "models": [{
                    "name": "huihui_ai/qwen2.5-coder-abliterate:3b",
                    "model": "huihui_ai/qwen2.5-coder-abliterate:3b",
                    "size": 100,
                    "details": {"parameter_size": "3B"},
                }]
            }),
            FakeResponse({"models": []}),
            FakeResponse({"details": {"family": "qwen2"}}),
        ]

        report = OllamaReadOnlyAudit().run()

        self.assertFalse(report["model_generation_performed"])
        self.assertFalse(report["downloads_performed"])
        self.assertFalse(report["configuration_changed"])
        self.assertEqual(report["sections"]["version"]["status"], "ok")
        self.assertEqual(
            report["sections"]["selected_model_details"]["status"],
            "ok",
        )
        self.assertEqual(mock_urlopen.call_count, 4)
        first_request = mock_urlopen.call_args_list[0].args[0]
        self.assertEqual(first_request.full_url, DEFAULT_ENDPOINT + "/api/version")
        self.assertEqual(first_request.get_method(), "GET")
        details_request = mock_urlopen.call_args_list[3].args[0]
        self.assertEqual(details_request.get_method(), "POST")
        self.assertIn('"model"', details_request.data.decode("utf-8"))

    @patch("src.model_audit.urlopen")
    def test_missing_selected_model_does_not_call_show(self, mock_urlopen):
        mock_urlopen.side_effect = [
            FakeResponse({"version": "test"}),
            FakeResponse({"models": [{"name": "other:latest"}]}),
            FakeResponse({"models": []}),
        ]

        report = OllamaReadOnlyAudit().run()

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(
            report["sections"]["selected_model_details"]["status"],
            "not_installed",
        )

    @patch("src.model_audit.urlopen")
    def test_partial_api_failure_is_reported(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = [
            URLError("offline"),
            FakeResponse({"models": []}),
            FakeResponse({"models": []}),
        ]

        report = OllamaReadOnlyAudit().run()

        self.assertEqual(report["sections"]["version"]["status"], "error")
        self.assertEqual(report["sections"]["installed_models"]["status"], "ok")

    def test_empty_selected_model_is_rejected(self):
        with self.assertRaises(AuditError):
            OllamaReadOnlyAudit(selected_model="  ")


if __name__ == "__main__":
    unittest.main()
