# Jarvis Coding Intelligence — Master Task Tracker

**Purpose:** Persistent source of truth for the ordered project roadmap. Keep the task order below stable unless the owner explicitly asks to reorder it. Update status and estimates only when there is new evidence.

**Completion notification rule:** When every task is complete and its acceptance criteria have been validated, explicitly notify the owner in the conversation that the full master task table is finished. Do not declare completion merely because code exists or CI passes. Distinguish implemented, unit-tested, integration-tested, and measured states.

**Progress figures are engineering estimates**, not measured performance results. They must not be presented as model-accuracy or resource-savings claims.

## Ordered master task table

| # | Task (preserve this order) | Current status | Estimated progress | Completion evidence required |
|---|---|---|---:|---|
| 1 | Local model inventory | Implemented; further validation possible | 85% | Inventory/metadata tests pass against installed Ollama models; no model downloads without approval. |
| 2 | Ollama client and timeout controls | Implemented | 85% | Unit tests cover bounds, timeout, invalid responses, and failures; integration tests do not require inference unless approved. |
| 3 | RAM protection | Implemented; real-world validation pending | 75% | Test known/low/unknown memory behavior, document fallback policy, and measure memory use under approved conditions. |
| 4 | Task routing | Implemented heuristics; effectiveness unproven | 60% | Reproducible comparison against a fixed profile shows whether routing improves outcomes without unacceptable resource cost. |
| 5 | Error analysis and correction proposals | Implemented; broader debugging evaluation pending | 70% | Representative failure cases produce bounded, relevant proposals without unsafe execution or unsupported claims. |
| 6 | Syntax verification | Implemented | 85% | Regression tests show malformed source is rejected and syntax-valid source is never mislabeled behaviorally verified. |
| 7 | Correction-to-verification workflow | Implemented in stacked draft PRs | 80% | Failure paths, verifier errors, malformed evidence, and successful evidence are tested; candidate code is never automatically applied. |
| 8 | Safe behavioral testing | Hardening in progress; real Windows/Docker smoke pending | 70% | Review isolation/cleanup, run CI tests, then complete guarded real-container smoke only when RAM and local-image prerequisites pass. |
| 9 | Verification evidence integrity | Actively hardened | 85% | Hash, trusted verifier identity, result shape, positive test count, timezone-aware timestamp, and ledger checks are covered; evidence-authenticity limits documented. |
| 10 | Learning ledger | Implemented; retrieval and conflict handling incomplete | 65% | Privacy, schema, append-only behavior, evidence checks, and safe retrieval/conflict policies have tests. |
| 11 | Prompt-injection resistance | Incomplete | 20% | Adversarial tests show untrusted code, logs, and model output cannot authorize privileged actions or bypass verification. |
| 12 | Coding benchmark | Initial smoke benchmark implemented | 25% | Fixed tasks with exact expected results, failure reporting, and reproducible runs exist; smoke results are not misrepresented as a broad benchmark. |
| 13 | RAM, CPU, and latency measurements | Pending | 10% | Repeatable measurements are collected under controlled conditions and include environment/configuration details. |
| 14 | Model and routing comparisons | Pending | 10% | Current model and already-installed alternatives are evaluated on identical tasks and resource budgets; no model pull without separate approval. |
| 15 | Multi-file debugging and learning effectiveness | Pending | 10% | Multi-file regression tasks and controlled with/without-learning comparisons establish whether reuse improves results. |
| 16 | Final integration into `main` | Not completed | 10% | Review stacked dependencies and combined diffs, require passing CI and agreed validation, and integrate only under the owner's existing authorization; never merge merely to clear the table. |

## Current hardening stack

- PR #17 — correction verification and learning workflow
- PR #18 — verifier subprocess pipe cleanup and bounded timeout handling
- PR #19 — cleanup after unexpected host-side verifier errors
- PR #20 — non-root Docker execution
- PR #21 — Docker RAM preflight
- PR #22 — strict workflow verification timestamps
- PR #23 — strict timezone-aware ledger timestamps
- PR #24 — timed-out verifier child-process-group cleanup
- PR #25 — private temporary verifier workspace permissions

These PRs are draft/unmerged unless GitHub status is checked and explicitly updated here. Never infer merge status from a populated merge-related field alone; verify the PR's `merged` state.

## Safety and reporting rules

1. Preserve this task order in progress reports.
2. Update status and estimates only with concrete evidence; keep estimates labeled as estimates.
3. Passing mocked unit tests does not prove real Docker behavior or model quality.
4. Do not run model inference, pull images/models, or perform a real Docker smoke test without checking current resource prerequisites and authorization.
5. Do not commit model weights.
6. Do not force-push, rewrite history, reset/clean destructively, overwrite user work, or merge draft PRs without explicit authorization.
7. Keep source verification, behavioral verification, and evidence authenticity distinct.
8. When all 16 tasks satisfy their acceptance criteria, tell the owner explicitly: **“The full Master Task Tracker is complete.”** Include remaining known limitations, if any, rather than hiding them.
