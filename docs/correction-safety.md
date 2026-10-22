# Jarvis Coding Intelligence — Correction Safety

## Current capabilities

- Local Ollama client restricted to loopback HTTP on port 11434.
- Bounded prompt and response sizes, request timeout, and no automatic retries.
- Conservative resource guard: available-RAM preflight, one inference at a
  time per Python process, bounded context/output/batch/thread settings, and a
  short model keep-alive.
- Heuristic fast/balanced/deep reasoning budgets, with deep mode reduced when
  RAM headroom is inadequate or cannot be measured.
- Deterministic classification of common error messages.
- Correction proposals generated from supplied code and failure evidence.
- Maximum of two proposal attempts per correction session.
- Non-executing Python syntax parsing with a source hash.
- Append-only JSONL learning ledger with compact hashes, bounded summaries,
  common secret-like text redaction, conservative UNVERIFIED/SYNTAX_VALID status,
  and VERIFIED disabled until trusted behavioral verification exists.
- No automatic file changes or execution of generated code.

## Resource guard limitations

The default minimum available-RAM threshold is 1536 MiB. When the platform
reports less, the client refuses to send an inference request and explains how
to recover. If the platform cannot report available memory, generation remains
bounded but the RAM preflight cannot be guaranteed. Deep mode is reduced to
balanced below 2048 MiB or when available memory is unknown. The in-process
lock prevents this client from running concurrent requests in one Python
process; it does not coordinate other applications or independent processes
that call Ollama directly. CPU thread limits apply to generation options but do
not cap total system CPU use.

## Learning ledger and verification policy

The default runtime ledger is data/learning_ledger.jsonl and is ignored by
Git. Records store a source SHA-256 hash, a bounded summary, a diagnostic
category, and a conservative status. Raw source code and raw failure output
are not stored.

The public append API accepts only UNVERIFIED records and rejects caller-
supplied verification dictionaries. SYNTAX_VALID is available only through a
dedicated method that independently parses the source before recording its
hash. Direct caller assignment of SYNTAX_VALID is rejected. VERIFIED is
currently disabled; it must not be restored until a trusted behavioral
verifier runs controlled tests and captures its own results. Do not store
secrets or private source in summaries. Redaction is best-effort, not a
guarantee.

A model proposal is not proof of a fix. Syntax validity is not behavioral
correctness. Before accepting a proposal, an independent verification stage
must review the exact change, run relevant tests in a controlled environment,
check for regressions, and record actual commands and exit codes. A failed or
unavailable test must never be recorded as a verified success.

## Safety boundary

The current syntax verifier uses Python's AST parser and never executes the
candidate. It is not a sandbox. Running arbitrary generated code directly on
the host would be unsafe and must not be added without a separately reviewed,
isolated execution design.
