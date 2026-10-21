# Jarvis Coding Intelligence

A lightweight local coding-intelligence project built around Ollama. The
project is being developed in small, test-backed stages for safer correction,
reproducible evaluation, verified learning, and resource-aware operation.

## Implemented

- Read-only Ollama model inventory and metadata audit.
- Local-only Ollama client with bounded prompt/response sizes.
- Conservative resource guard: RAM preflight, serialized inference, bounded
  context/output/batch/thread settings, and short model keep-alive.
- Deterministic error classification.
- Bounded correction proposals (at most two attempts).
- Non-executing Python syntax verification.
- Unit tests and Python 3.10–3.13 CI.

The resource guard reduces avoidable memory use; it cannot guarantee that
Windows or Ollama will never use high CPU or RAM. If measured available RAM is
below 1536 MiB, inference is paused before a request is sent. This default
threshold is configurable as documented below.

These features do not yet constitute behavioral self-correction, persistent
verified learning, or a model benchmark. No candidate model is considered
stronger until it is tested on the same reproducible coding tasks and resource
measurements as the current model.

## Resource controls

The default settings are intentionally conservative for an 8 GB computer:

| Environment variable | Default | Allowed range | Effect |
| --- | ---: | ---: | --- |
| `JARVIS_MIN_FREE_RAM_MB` | `1536` | 512–4096 | Pause inference below this much available RAM |
| `JARVIS_OLLAMA_NUM_CTX` | `2048` | 512–4096 | Limits context window; lower usually reduces KV-cache RAM |
| `JARVIS_OLLAMA_NUM_PREDICT` | `384` | 64–1024 | Caps generated tokens per request |
| `JARVIS_OLLAMA_NUM_BATCH` | `128` | 32–256 | Limits prompt-processing batch size |
| `JARVIS_OLLAMA_NUM_THREAD` | `2` | 1–4 | Limits inference CPU threads |
 
For example, in PowerShell (current terminal only):

```powershell
$env:JARVIS_OLLAMA_NUM_CTX = "1024"
$env:JARVIS_OLLAMA_NUM_PREDICT = "256"
$env:JARVIS_OLLAMA_NUM_THREAD = "2"
```

Lower settings may reduce answer length or coding capability. The RAM threshold
is not lowered automatically because doing so can make the computer unstable.
Requests through this client are serialized to avoid concurrent model loads.
Ollama is asked to unload the model after 30 seconds of inactivity; this saves
idle RAM but can make the next request slower because the model may need to
load again. Existing Ollama settings and other applications are not changed.

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

This makes one inference request and may temporarily increase RAM use. The
resource guard can refuse it if available RAM is below the configured minimum.

```powershell
python -m tests.real_ollama_smoke_test
```

See [docs/model-audit.md](docs/model-audit.md) and
[docs/correction-safety.md](docs/correction-safety.md) for scope and limits.
