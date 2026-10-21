# Jarvis Coding Intelligence

A lightweight local coding-intelligence project built around Ollama. The
project is being developed in small, test-backed stages for safer correction,
reproducible evaluation, verified learning, and resource-aware operation.

## Implemented

- Read-only Ollama model inventory and metadata audit.
- Local-only Ollama client with bounded prompt/response sizes and finite,
  bounded request timeouts.
- Conservative resource guard: RAM preflight, serialized inference, bounded
  context/output/batch/thread settings, and short model keep-alive.
- Resource-aware task routing: fast, balanced, and deep reasoning budgets.
- Deterministic error classification and bounded correction proposals.
- Non-executing Python syntax verification.
- Append-only, privacy-conscious learning ledger with evidence-gated VERIFIED
  records.
- Small deterministic coding smoke checks (not a reliable accuracy benchmark).
- Unit tests and Python 3.10–3.13 CI.

The resource guard reduces avoidable memory use; it cannot guarantee that
Windows or Ollama will never use high CPU or RAM. If measured available RAM is
below 1536 MiB, inference is paused before a request is sent. This default
threshold is configurable as documented below.

These features do not yet constitute behavioral self-correction or a reliable
coding-model accuracy benchmark. The smoke checks use simple response markers;
they can accept incorrect code and do not execute generated code. The ledger
records caller-supplied evidence but does not run tests itself and cannot prove
that evidence is genuine. No candidate model is considered stronger until it
is tested on the same reproducible coding tasks and resource measurements as
the current model.

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
too low. Task routing is heuristic, not a measure of intelligence, and must be
benchmarked against real coding tasks before claiming better accuracy.

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

The Ollama client request timeout defaults to 90 seconds. Explicit timeouts
must be finite, greater than zero, and no more than 600 seconds; NaN, infinity,
and larger values are rejected during client construction.

## Verified learning ledger

The runtime ledger defaults to `data/learning_ledger.jsonl`, which is ignored
by Git. Each entry stores a source hash, diagnostic category, bounded summary,
and status. A VERIFIED record additionally requires caller-supplied commands,
zero exit code, a positive test count, and an ISO timestamp. The ledger does
not execute tests and does not independently prove that supplied evidence is
genuine. It never stores the full source code or raw failure output by design.

## Coding smoke checks

The smoke-check runner is opt-in and sends three small requests to the selected
local Ollama model. It does not download a model or execute generated code.
The resource guard may refuse the requests when available RAM is too low.
These marker-based checks are useful for a quick wiring check, not for proving
model quality or selecting a winning model.

In PowerShell, run unit tests first. Only run the model checks when the laptop
has adequate free RAM and Ollama is running:

```powershell
python -m unittest discover -s tests -v
python -m src.benchmark --run
```

To test another model that is already installed, specify its exact Ollama name:

```powershell
python -m src.benchmark --run --model "qwen3.5:2b"
```

The command requires `--run` deliberately. Without that flag, it prints help
and performs no inference. Run each candidate separately and do not compare
scores as definitive accuracy measurements.

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
