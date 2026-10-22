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

**Engineering policy:** Resource efficiency must not silently degrade reasoning,
coding accuracy, debugging reliability, security, or verification. Material
optimizations require a reproducible baseline and quality/performance comparison;
see [the resource-efficiency and quality policy](docs/RESOURCE_EFFICIENCY_AND_QUALITY.md).

These features do not yet constitute behavioral self-correction or a reliable
coding-model accuracy benchmark. The smoke checks validate selected Python AST
structures for the three built-in tasks; they do not execute generated code or
prove full semantic correctness. The ledger records caller-supplied evidence
but does not run tests itself and cannot prove that evidence is genuine. No
candidate model is considered stronger until it is tested on the same
reproducible coding tasks and resource measurements as the current model.

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

## Prompt-injection boundary

Correction inputs are serialized as a compact JSON object and explicitly treated
as untrusted data. Task text, source, comments, logs, and analyzer excerpts may
contain instruction-like content; the prompt tells the model not to treat those
values as authority. This is defense in depth only: prompt text and unit tests
cannot prove resistance to a capable model's prompt injection. Authorization,
verification, execution, and file-writing controls remain outside model output.

## Verified learning ledger

The runtime ledger defaults to `data/learning_ledger.jsonl`, which is ignored
by Git. Each entry stores a source hash, diagnostic category, bounded summary,
and status. A VERIFIED record additionally requires caller-supplied commands,
zero exit code, a positive test count, and an ISO timestamp. The ledger does
not execute tests and does not independently prove that supplied evidence is
genuine. It never stores the full source code or raw failure output by design.

## Correction workflow coordinator

`src/correction_workflow.py` connects one bounded correction proposal to strict
proposal extraction, Python syntax validation, optional behavioral-verifier
handoff, and learning-ledger recording. The model must return exactly one
fenced Python replacement in the `PROPOSED FIX` section. Ambiguous output is
not executed or recorded as verified.

Without a configured behavioral verifier, the workflow records at most
`SYNTAX_VALID`; syntax validity is not behavioral correctness. A verifier must
be trusted integration code that tests the exact candidate source in a suitably
restricted environment and returns its source hash, configured verifier ID,
run ID, test command(s), exit code, test count, check names, and timestamp.
The coordinator checks the hash and configured identity before allowing a
`VERIFIED` ledger record. The ledger stores that provenance in schema version 2.

**Safety boundary:** The coordinator does not write or execute candidate code.
This repository includes the optional, narrow Docker-based behavioral verifier
described below; it is not a general project test runner, requires an image
already installed locally, and real Windows/Docker Desktop behavior remains
unverified until the guarded smoke test is performed. A test double used by unit
tests verifies orchestration logic only; it is not evidence that real generated
code passed behavioral tests. Direct ledger calls still cannot cryptographically
prove that caller-supplied evidence is genuine.

### Optional Docker behavioral verifier

`src/docker_verifier.py` provides an opt-in adapter for a single module-level
Python function whose arguments, keyword arguments, and return value are JSON
compatible. Supply trusted input/expected-output cases and configure
`DockerFunctionVerifier` as the `CorrectionWorkflow` behavioral verifier. It
checks each case in a separate Python child process inside a Docker container.
Each case has a two-second timeout; on timeout, the runner makes a best-effort
attempt to terminate the child's process group and reap the direct child before
continuing. This is not a guarantee against descendants that deliberately escape
their process group; Docker's overall process, memory, CPU, and container-runtime
limits remain additional containment layers.

The image must already exist locally: the adapter checks it with
`docker image inspect` and uses `--pull=never`; it never downloads an image.
The container has no network, a read-only root filesystem and source mount,
256 MiB memory, 0.5 CPU, a 32-process limit, dropped capabilities, no-new-
privileges, a bounded runtime, and bounded host-captured output. On POSIX,
the container runs as the current non-root host UID/GID so the temporary source
workspace can remain owner-only (directory mode 0700, files mode 0600); the
verifier refuses to start from a root host process rather than making source
files world-readable. Windows uses the unprivileged Docker Desktop fallback and
still requires the guarded smoke test to validate bind-mount behavior. Expected
values are held by the container-side runner and are not sent to the candidate
process.

This is a **narrow initial verifier**, not a general project test runner. It
cannot verify arbitrary multi-file changes or replace a repository's trusted
test suite. Docker/container vulnerabilities remain a residual risk. CI mocks
Docker calls; a real container run is not claimed unless separately performed.

To validate the local Docker setup with a fixed, harmless `add()` example, run
the help-only command first:

```powershell
python -m scripts.docker_verifier_smoke
```

Only if Docker is available, the required image is already installed, and at
least 1536 MiB of physical RAM is free, explicitly run:

```powershell
python -m scripts.docker_verifier_smoke --run
```

The smoke script does not call Ollama, download an image, or use model-generated
code. It fails closed when RAM cannot be measured or is below the threshold.

Example configuration (does not run until the workflow is explicitly invoked):

```python
from src.docker_verifier import DockerFunctionVerifier

verifier = DockerFunctionVerifier(
    function_name="add",
    test_cases=[
        {"args": [1, 2], "kwargs": {}, "expected": 3},
        {"args": [-2, 5], "kwargs": {}, "expected": 3},
    ],
    image="python:3.12-slim",  # must already be present locally
)
# Pass verifier and verifier.verifier_id to CorrectionWorkflow.
```

## Coding smoke checks

The smoke-check runner is opt-in and sends three small requests to the selected
local Ollama model. It does not download a model or execute generated code.
For the built-in tasks, Python's AST parser checks the requested function,
dictionary lookup, or list-comprehension structure. These checks are stronger
than searching for text markers, but still do not prove runtime behavior or
full semantic correctness. The resource guard may refuse requests when
available RAM is too low.

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
