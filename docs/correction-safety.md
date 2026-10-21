# Jarvis Coding Intelligence — Correction Safety

## Current capabilities

- Local Ollama client restricted to loopback HTTP on port 11434.
- Bounded prompt and response sizes, request timeout, and no automatic retries.
- Conservative resource guard: available-RAM preflight, one inference at a
  time per Python process, bounded context/output/batch/thread settings, and a
  short model keep-alive.
- Deterministic classification of common error messages.
- Correction proposals generated from supplied code and failure evidence.
- Maximum of two proposal attempts per correction session.
- Non-executing Python syntax parsing with a source hash.
- No automatic file changes or execution of generated code.
- Proposals remain unverified by default.

## Resource guard limitations

The default minimum available-RAM threshold is 1536 MiB. When the platform
reports less, the client refuses to send an inference request and explains how
to recover. If the platform cannot report available memory, the request still
uses bounded generation settings but the RAM preflight cannot be guaranteed.
The in-process lock prevents this client from running concurrent requests in
one Python process; it does not coordinate other applications or independent
processes that call Ollama directly. CPU thread limits apply to generation
options but do not cap total system CPU use.

## Verification policy

A model proposal is not proof of a fix. Syntax validity is not behavioral
correctness. Before accepting a proposal, an independent verification stage
must review the exact change, run relevant tests in a controlled environment,
check for regressions, and record actual commands and exit codes.

A failed or unavailable test must never be recorded as a verified success.
Persistent verified learning is not implemented yet.

## Safety boundary

The current syntax verifier uses Python's AST parser and never executes the
candidate. It is not a sandbox. Running arbitrary generated code directly on
the host would be unsafe and must not be added without a separately reviewed,
isolated execution design.
