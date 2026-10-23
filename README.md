# Jarvis Coding Intelligence

A lightweight local coding-intelligence project built around Ollama, with an
emphasis on evidence-based correction, verification, persistent learning, and
resource-aware operation.

## Current implementation

- **Read-only model audit:** inventories the local Ollama version, installed
  models, currently loaded models, and selected-model metadata.
- **Local-only endpoint policy:** the audit client only accepts loopback HTTP
  on port 11434.
- **Bounded requests:** API timeouts and response-size limits are enforced.
- **No model mutation:** the audit does not generate text, download models, or
  change Ollama configuration.
- **Automated tests:** GitHub Actions runs the standard-library unit tests on
  Python 3.10–3.13.

## Run the model audit

Requires Python 3.10+ and a locally running Ollama service.

```powershell
python -m src.model_audit
```

The report is an inventory, not a benchmark. It cannot by itself establish
that a model is newer, more accurate, less restrictive, or stronger. Model
candidates must be evaluated separately using repeatable coding tasks and
resource measurements.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

See [docs/model-audit.md](docs/model-audit.md) for audit scope and limitations.
