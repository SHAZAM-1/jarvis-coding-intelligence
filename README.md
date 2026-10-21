# Jarvis Coding Intelligence

A lightweight local coding-intelligence project built around Ollama. The
project is being developed in small, test-backed stages for safer correction,
reproducible evaluation, verified learning, and resource-aware operation.

## Implemented

- Read-only Ollama model inventory and metadata audit.
- Local-only Ollama client with bounded prompt/response sizes.
- Conservative resource guard: RAM preflight, serialized inference, bounded
  context/output/batch/thread settings, and short model keep-alive.
- Resource-aware task routing: fast, balanced, and deep reasoning budgets.
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

## Adaptive reasoning and resource controls

Jarvis chooses a generation budget from simple, inspectable task signals:

| Profile | Context | Output cap | Batch | Intended use |
| --- | ---: | ---: | ---: | --- |
| `fast` | 1,024 | 192 tokens | 64 | Simple explanations and small requests |
| `balanced` | 2,048 | 384 tokens | 128 | Default coding and debugging |
| `deep` | 4,096 | 768 tokens | 128 | Complex debugging, regression analysis, and code review |

All profiles default to 2 inference threads. Deep mode is automatically reduced
to balanced when available RAM is below 2,048 MiB or cannot be measured. The
separate 1,536 MiB minimum-RAM preflight still blocks inference when memory is
too low. Task routing is heuristic, not a measure of intelligence, and it must
be benchmarked against real coding tasks before claiming better accuracy.

| Environment variable | Default | Allowed range | Effect |
| --- | ---: | ---: | --- |
| `JARVIS_MIN_FREE_RAM_MB` | `1536` | 512–4096 | Pause inference below this much available RAM |
| `JARVIS_OLLAMA_NUM_CTX` | Profile-dependent | 512–4096 | Explicit context override |
| `JARVIS_OLLAMA_NUM_PREDICT` | Profile-dependent | 64–1024 | Explicit output-token override |
| `JARVIS_OLLAMA_NUM_BATCH` | Profile-dependent | 32–256 | Explicit batch-size override |
| `JARVIS_OLLAMA_NUM_THREAD` | `2` | 1–4 | Explicit inference-thread override |

For example, in PowerShell (current terminal only):

```powershell
$env:JARVIS_OLLAMA_NUM_CTX = "1024"
$env:JARVIS_OLLAMA_NUM_PREDICT = "256"
$env:JARVIS_OLLAMA_NUM_THREAD = "2"
```

Explicit environment overrides take precedence over profile defaults but remain
clamped to safe ranges. Lower settings may reduce answer length or coding
capability. The RAM threshold is not lowered automatically because doing so can
make the computer unstable. Requests through this client are serialized to
avoid concurrent model requests. Ollama is asked to unload the model after 30
seconds of inactivity; this saves idle RAM but can make the next request slower
because the model may need to load again. Existing Ollama settings and other
applications are not changed.

## Model accuracy and updates

Prompting and resource controls do not change model weights. Jarvis must not
claim that its underlying model became smarter just because it uses a deeper
profile. Before replacing model weights, compare the existing model with an
already-installed candidate using the same fixed coding/debugging tasks, exact
expected results, timeouts, peak RAM, and response latency. Only pull a new
model after a separate resource check confirms adequate disk and memory.

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
