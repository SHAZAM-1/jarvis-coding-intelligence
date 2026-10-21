# Jarvis Coding Intelligence — Correction Safety

## Current capabilities

- Local Ollama client restricted to loopback HTTP on port 11434.
- Bounded prompt and response sizes, request timeout, and no automatic retries.
- Deterministic classification of common error messages.
- Correction proposals generated from supplied code and failure evidence.
- Maximum of two proposal attempts per correction session.
- Non-executing Python syntax parsing with a source hash.
- No automatic file changes or execution of generated code.
- Proposals remain unverified by default.

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
