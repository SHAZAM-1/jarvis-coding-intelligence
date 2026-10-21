"""Minimal, local-only Ollama client with a conservative resource budget."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.resource_guard import generation_options, inference_slot


DEFAULT_MODEL = "huihui_ai/qwen2.5-coder-abliterate:3b"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
MAX_PROMPT_BYTES = 131072
MAX_RESPONSE_BYTES = 1048576


class OllamaClientError(RuntimeError):
    """Raised when an Ollama request cannot be completed safely."""


class OllamaClient:
    """Send bounded, serialized requests to a local Ollama server."""

    def __init__(self, model=None, endpoint=None, timeout=90):
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.endpoint = (
            endpoint or os.getenv("OLLAMA_HOST", DEFAULT_ENDPOINT)
        ).rstrip("/")
        self.timeout = timeout

        parsed = urlparse(self.endpoint)
        allowed_hosts = {"127.0.0.1", "localhost", "::1"}

        try:
            correct_port = parsed.port == 11434
        except ValueError:
            correct_port = False

        if (
            parsed.scheme != "http"
            or parsed.hostname not in allowed_hosts
            or not correct_port
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Ollama endpoint must be local HTTP on port 11434."
            )

        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Model name must be a non-empty string.")

        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise ValueError("Timeout must be a positive number.")

    def generate(self, prompt):
        """Generate one bounded response; never retry or stream requests."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        prompt_bytes = prompt.encode("utf-8")
        if len(prompt_bytes) > MAX_PROMPT_BYTES:
            raise ValueError(
                f"Prompt exceeds the {MAX_PROMPT_BYTES}-byte limit."
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30s",
            "options": generation_options(),
        }
        request = Request(
            f"{self.endpoint}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            # The process-wide slot prevents concurrent calls from multiplying
            # model memory use. The RAM check runs immediately before inference.
            with inference_slot():
                with urlopen(request, timeout=self.timeout) as response:
                    raw_response = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise OllamaClientError(
                f"Ollama returned HTTP {exc.code}."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaClientError(
                "Could not reach local Ollama. Check that Ollama is running."
            ) from exc

        if len(raw_response) > MAX_RESPONSE_BYTES:
            raise OllamaClientError(
                f"Ollama response exceeds the {MAX_RESPONSE_BYTES}-byte limit."
            )

        try:
            result = json.loads(raw_response.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OllamaClientError(
                "Ollama returned invalid JSON or text encoding."
            ) from exc

        if not isinstance(result, dict):
            raise OllamaClientError("Ollama response must be a JSON object.")

        text = result.get("response")
        if not isinstance(text, str):
            raise OllamaClientError(
                "Ollama response is missing its text field."
            )
        return text
