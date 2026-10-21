"""Read-only inventory audit for a local Ollama installation.

This module does not generate model output, download models, or modify Ollama.
Only loopback HTTP endpoints on port 11434 are permitted.
"""
from __future__ import annotations

import json
import math
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_SELECTED_MODEL = "huihui_ai/qwen2.5-coder-abliterate:3b"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class AuditError(RuntimeError):
    """Raised when the audit configuration or response is invalid."""


def validate_local_endpoint(endpoint: str) -> str:
    """Validate and normalize a loopback-only Ollama endpoint."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise AuditError("Endpoint must be a non-empty string.")

    try:
        parsed = urlsplit(endpoint.strip())
        port = parsed.port
    except ValueError as exc:
        raise AuditError("Endpoint URL is invalid.") from exc

    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port != 11434
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise AuditError(
            "Only local HTTP endpoints on port 11434 are allowed."
        )

    host = parsed.hostname
    if host == "localhost":
        # Keep the supplied loopback hostname; do not resolve or contact
        # any external address during configuration validation.
        normalized_host = "localhost"
    elif host == "::1":
        normalized_host = "[::1]"
    else:
        normalized_host = "127.0.0.1"

    return f"http://{normalized_host}:11434"


class OllamaReadOnlyAudit:
    """Collect Ollama version, installed model, and loaded-model metadata."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        selected_model: str = DEFAULT_SELECTED_MODEL,
        timeout: float = 5.0,
    ) -> None:
        self.endpoint = validate_local_endpoint(endpoint)
        if not isinstance(selected_model, str) or not selected_model.strip():
            raise AuditError("Selected model must be a non-empty string.")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise AuditError("Timeout must be a finite positive number.")
        try:
            timeout_value = float(timeout)
        except (OverflowError, ValueError) as exc:
            raise AuditError("Timeout must be a finite positive number.") from exc
        if not math.isfinite(timeout_value) or timeout_value <= 0 or timeout_value > 60:
            raise AuditError("Timeout must be finite, greater than 0, and at most 60 seconds.")
        self.selected_model = selected_model.strip()
        self.timeout = timeout_value

    def _request_json(self, path: str, payload: dict | None = None) -> dict:
        if not path.startswith("/") or ".." in path.split("/"):
            raise AuditError("Invalid local API path.")

        data = None
        method = "GET"
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            method = "POST"
            headers["Content-Type"] = "application/json"

        request = Request(
            self.endpoint + path,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise AuditError(f"Local Ollama request failed for {path}: {exc}") from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise AuditError(f"Local Ollama response exceeded {MAX_RESPONSE_BYTES} bytes.")

        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditError(f"Local Ollama returned invalid JSON for {path}.") from exc

        if not isinstance(result, dict):
            raise AuditError(f"Local Ollama returned a non-object response for {path}.")
        return result

    def run(self) -> dict:
        """Run a bounded, read-only audit; report partial failures per section."""
        report = {
            "audit_type": "read_only_local_ollama_inventory",
            "endpoint": self.endpoint,
            "selected_model": self.selected_model,
            "model_generation_performed": False,
            "downloads_performed": False,
            "configuration_changed": False,
            "sections": {},
        }

        for section, path in (
            ("version", "/api/version"),
            ("installed_models", "/api/tags"),
            ("loaded_models", "/api/ps"),
        ):
            try:
                report["sections"][section] = {
                    "status": "ok",
                    "data": self._request_json(path),
                }
            except AuditError as exc:
                report["sections"][section] = {
                    "status": "error",
                    "error": str(exc),
                }

        installed = report["sections"].get("installed_models", {})
        model_items = installed.get("data", {}).get("models", [])
        if not isinstance(model_items, list):
            model_items = []

        matches = [
            item for item in model_items
            if isinstance(item, dict)
            and self.selected_model in {
                item.get("name"),
                item.get("model"),
            }
        ]

        if not matches:
            report["sections"]["selected_model_details"] = {
                "status": "not_installed",
                "message": "Selected model was not found in the installed model inventory.",
            }
        else:
            try:
                details = self._request_json(
                    "/api/show",
                    {"model": self.selected_model},
                )
                report["sections"]["selected_model_details"] = {
                    "status": "ok",
                    "data": details,
                }
            except AuditError as exc:
                report["sections"]["selected_model_details"] = {
                    "status": "error",
                    "error": str(exc),
                }

        return report


def main() -> int:
    """Print an audit report as JSON without changing the local installation."""
    audit = OllamaReadOnlyAudit()
    report = audit.run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if any(
        section.get("status") == "ok"
        for section in report["sections"].values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
