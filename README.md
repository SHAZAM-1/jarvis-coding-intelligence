# Jarvis Coding Intelligence

A lightweight local coding-intelligence project built around Ollama. The
project is being developed in small, test-backed stages for safer correction,
reproducible evaluation, verified learning, and resource-aware operation.

## Implemented

- Read-only Ollama model inventory and metadata audit.
- Local-only Ollama client with bounded prompt/response sizes.
- Deterministic error classification.
- Bounded correction proposals (at most two attempts).
- Non-executing Python syntax verification.
- Unit tests and Python 3.10–3.13 CI.

These features do not yet constitute behavioral self-correction, persistent
verified learning, or a model benchmark. No candidate model is considered
stronger until it is tested on the same reproducible coding tasks and resource
measurements as the current model.

## Run audit

Requires Python 3.10+ and a locally running Ollama service:

```powershell
python -m src.model_audit
```

## Run unit tests

```powershell
python -m unittest discover -s tests -v
```

## Optional real-model smoke test

This makes one inference request and may temporarily increase RAM use:

```powershell
python -m tests.real_ollama_smoke_test
```

See [docs/model-audit.md](docs/model-audit.md) and
[docs/correction-safety.md](docs/correction-safety.md) for scope and limits.
