"""Optional one-request smoke test against the local Ollama service."""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model_client import OllamaClient, OllamaClientError

MODEL = "huihui_ai/qwen2.5-coder-abliterate:3b"
PROMPT = "Reply with exactly this text: JARVIS_CONNECTION_OK"


def main():
    print("=== JARVIS REAL MODEL CONNECTION TEST ===")
    print("Project:", PROJECT_ROOT)
    print("Model:", MODEL)
    print("Sending one request to local Ollama...")
    start = time.monotonic()
    try:
        client = OllamaClient(
            model=MODEL, endpoint="http://127.0.0.1:11434", timeout=120
        )
        response = client.generate(PROMPT)
    except (OllamaClientError, ValueError) as exc:
        print("\nRESULT: FAIL")
        print("Reason:", exc)
        return 1
    elapsed = time.monotonic() - start
    print("\n=== MODEL RESPONSE ===")
    print(response)
    print("======================")
    print(f"Elapsed time: {elapsed:.2f} seconds")
    if "JARVIS_CONNECTION_OK" in response:
        print("\nRESULT: PASS")
        print("Python successfully communicated with the real model.")
        return 0
    print("\nRESULT: REVIEW")
    print("The model responded, but the expected token was missing.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
