# Read-only local model audit

The model audit collects metadata from an Ollama instance running on the same
computer. It does not generate model output, pull or delete models, or modify
Ollama configuration.

## Run

From the repository root with Python 3.10 or newer:

```powershell
python -m src.model_audit
```

The report includes:
- Ollama version, when available.
- Installed model inventory and metadata returned by Ollama.
- Models currently loaded in memory.
- Detailed metadata for the configured selected model, if installed.
- Per-section errors when the local API is unavailable.

The client only permits HTTP loopback endpoints on port 11434. The timeout and
response size are bounded. API responses are treated as data and are never
executed.

## Scope and limitations

This is an inventory audit, not a coding-quality benchmark. It cannot prove
that a model is current, uncensored, accurate, or stronger than another model.
Those claims require a separate, reproducible benchmark and an explicit review
of candidate models and their metadata. No model is downloaded or updated by
this tool.
