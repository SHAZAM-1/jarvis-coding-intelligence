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
| 4 | Task routing | Implemented heuristics; effectiveness unproven | 60% | Reproducible comparison against a fixed profile shows whether routing improves outcomes without unacceptable resource cost or quality regression. |
| 5 | Error analysis and correction proposals | Implemented; broader debugging evaluation pending | 70% | Representative failure cases produce bounded, relevant proposals without unsafe execution or unsupported claims; record task success and regressions. |
| 6 | Syntax verification | Implemented | 85% | Regression tests show malformed source is rejected and syntax-valid source is never mislabeled behaviorally verified. |
| 7 | Correction-to-verification workflow | Implemented in stacked draft PRs | 80% | Failure paths, verifier errors, malformed evidence, and successful evidence are tested; candidate code is never automatically applied. |
| 8 | Safe behavioral testing | Hardening in progress; real Windows/Docker smoke pending | 70% | Review isolation/cleanup, run CI tests, then complete guarded real-container smoke only when RAM and local-image prerequisites pass. |
| 9 | Verification evidence integrity | Actively hardened | 85% | Hash, trusted verifier identity, result shape, positive test count, timezone-aware timestamp, and ledger checks are covered; evidence-authenticity limits documented. |
| 10 | Learning ledger | Implemented; retrieval and conflict handling incomplete | 65% | Privacy, schema, append-only behavior, evidence checks, and safe retrieval/conflict policies have tests. Cache/reuse behavior, if added, must have freshness and invalidation tests. |
| 11 | Prompt-injection resistance | Incomplete | 20% | Adversarial tests show untrusted code, logs, and model output cannot authorize privileged actions or bypass verification. |
| 12 | Coding benchmark | Initial smoke benchmark implemented | 25% | Fixed tasks with exact expected results, failure reporting, and reproducible runs exist; quality and resource outcomes are evaluated separately; smoke results are not misrepresented as a broad benchmark. |
| 13 | RAM, CPU, and latency measurements | Pending | 10% | Reproducible baseline and repeated measurements include hardware/software, workload, warm/cold state, available/peak RAM, CPU, latency, concurrency, and method; report uncertainty and limitations. |
| 14 | Model and routing comparisons | Pending | 10% | Current model and already-installed alternatives are evaluated on identical tasks, quality criteria, and resource budgets; reject optimizations that exceed agreed quality-regression tolerance; no model pull without separate approval. |
| 15 | Multi-file debugging and learning effectiveness | Pending | 10% | Multi-file regression tasks and controlled with/without-learning comparisons measure task success, regressions, repeated-run stability, resource pressure, timeout/cancellation recovery, and whether reuse improves results. |
| 16 | Final integration into `main` | Not completed | 10% | Review stacked dependencies and combined diffs, require passing CI and agreed validation, and integrate only under the owner's existing authorization; never merge merely to clear the table. |

## Mandatory engineering principle: resource efficiency without quality degradation

The governing objective is **maximize useful intelligence per unit of resource consumed; minimize waste, not capability**. Priority order is correctness/reliability, security/data integrity, reasoning quality/task completion, efficient resource use, then convenience. Do not silently trade away mandatory tests, security, verification, or task completeness for lower RAM, CPU, latency, or token usage.

The full policy and acceptance protocol are documented in [RESOURCE_EFFICIENCY_AND_QUALITY.md](RESOURCE_EFFICIENCY_AND_QUALITY.md). In brief:

- Measure the actual target machine and representative workload before material optimization; do not invent metrics or assume smaller models/caches/quantization are better.
- Record method, environment, available/peak RAM, CPU, latency, task success, regression count, and relevant concurrency/background activity.
- Optimize duplicate work, redundant inference, unnecessary scans, unsafe/stale caching, repeated model loading, and unhelpful concurrency before reducing model capability or essential context.
- Route by evidence, use installed/configured models, preserve reliable fallbacks, and escalate selectively for difficult or uncertain tasks. No model downloads without separate approval.
- Apply backpressure under resource pressure: stop optional work, reduce concurrency, prefer incremental/sequential execution, and report blocked work honestly. Preserve mandatory correctness and security checks.
- Accept material optimizations only when resource gains are reproducible and quality remains within documented tolerances. If quality is not adequately measured, label the optimization **provisional**.
- Completion requires a documented baseline, measured resource improvement (or an evidence-backed finding that an optimization did not help), no material quality regression, passing required tests, stable repeated-task behavior under realistic pressure, safe timeout/cancellation/low-memory recovery, and evidence-backed documentation updates.

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
8. Resource savings do not prove quality preservation; use a repeatable benchmark and report uncertainty.
9. When all 16 tasks satisfy their acceptance criteria, tell the owner explicitly: **“The full Master Task Tracker is complete.”** Include remaining known limitations, if any, rather than hiding them.
