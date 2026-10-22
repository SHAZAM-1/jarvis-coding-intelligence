# Jarvis Coding Intelligence — Full Project Task Master Audit

**Repository:** SHAZAM-1/jarvis-coding-intelligence  
**Audit date:** 2026-10-22  
**Scope:** Current status, architecture, updates, model impact, missing capabilities, engineering gaps, active work, architectural limitations, and roadmap.

> **Evidence policy:** This document distinguishes implemented code, CI evidence, local verification, measured outcomes, and planned work. Passing unit tests does not prove coding accuracy. Prompting, routing, validation, and workflow improvements do not themselves change model weights. Do not claim accuracy gains or RAM savings without reproducible measurements.

## Executive summary

Jarvis has a useful modular foundation: local Ollama client, resource guard, heuristic task router, error analyzer, bounded correction proposals, non-executing Python syntax checks, learning ledger, model inventory, and opt-in coding smoke benchmark.

The main limitation is **integration and evidence**. The components do not yet form a complete end-to-end process that reliably distinguishes a proposed fix from a behaviorally correct, independently verified fix and then records evidence for future reuse. The three-task benchmark is a smoke check, not a general coding-ability measure.

### Progress update — 2026-10-22: correction workflow implementation started

A new implementation branch, `feat/correction-verification-learning-workflow`,
is building the first safe coordinator slice in draft PR #17. GitHub Actions
run #239 passed on Python 3.10, 3.11, 3.12, and 3.13; the Python 3.10 job ran
106 unit tests. The subsequent run #245 exposed a test assertion that assumed
the prompt phrase was on one line after the instruction was intentionally
wrapped for readability. The assertion is being corrected to normalize
whitespace; no runtime failure was identified in that run. The slice strictly
extracts one Python code block from the model's `PROPOSED FIX` section, applies the existing
non-executing syntax gate, optionally delegates behavioral checks to a configured
trusted adapter, checks the returned source hash and verifier identity, and
records provenance in the learning ledger.

This remains an incremental behavioral-verification solution. The opt-in
`DockerFunctionVerifier` provides a restricted, network-disabled test adapter
for pure JSON-callable functions, with bounded CPU, memory, processes, runtime,
and output. GitHub Actions run #279 passed all four supported Python versions; the Python
3.10 job ran 126 tests, including the workflow-to-Docker-adapter integration
test and extreme-timeout validation. CI mocks the Docker boundary, so no real
container run is claimed. It does not cover arbitrary project tests. Without a
configured verifier, outcomes remain `SYNTAX_VALID` or `UNVERIFIED`, never
`VERIFIED`.

Recommended order: verify the latest branch locally; review stacked PR dependencies; integrate correction with safe verification; make learning records evidence-backed; expand behavioral benchmarking; measure resource use; compare model/routing choices only after repeatable measurements; then integrate reviewed changes into main without bypassing safeguards.

## 1. Current project status

| ID | Component / task | Current status | Evidence / limitation | Next action | Priority |
|---|---|---|---|---|---|
| P-01 | Read-only Ollama model audit | Implemented in draft PR | Inventories local models; does not establish coding quality | Verify and integrate after dependency review | High |
| P-02 | Ollama model client | Implemented | Local-only endpoint, bounded requests/responses, timeout validation, no automatic retries | Review failure handling and integration tests | High |
| P-03 | Resource budget guard | Implemented in draft PR | RAM preflight and bounded profiles; actual savings unmeasured | Measure RAM, CPU, and latency | Critical |
| P-04 | Task router | Implemented | Heuristic routing selects fast/balanced/deep profile | Evaluate against fixed-profile baselines | High |
| P-05 | Error analyzer | Implemented | Classifies common errors; ambiguous/unseen errors can be misclassified | Expand tests and preserve unknown cases | High |
| P-06 | Self-correction engine | Implemented | Produces bounded proposals; does not apply changes or prove correctness | Connect proposals to independent verification | Critical |
| P-07 | Syntax verification | Implemented | Parses Python without executing it | Keep as an early gate; add separate behavioral testing | Critical |
| P-08 | Learning ledger | Implemented; provenance strengthened in workflow branch | Append-only records, bounded summaries, secret-like text redaction; schema v2 stores source hash, verifier ID/run ID, and check names | Keep direct-API trust caveat explicit; add safe retrieval | Critical |
| P-09 | Coding smoke benchmark | Implemented in draft PR | Three fixed tasks; narrow coverage | Expand into behavioral benchmark | Critical |
| P-10 | AST validation | Implemented in draft PR | Checks structure for built-in benchmark tasks | Verify locally; extend regression coverage | High |
| P-11 | Strict AST/audit-timeout checks | Implemented in PR #7 | GitHub Actions passed on recorded head; local verification still outstanding in latest known status | Run local tests and inspect Git status | High |
| P-12 | End-to-end correction workflow | In progress in workflow branch | Coordinator connects proposal extraction, syntax validation, optional trusted-verifier handoff, and ledger recording | Add a real restricted behavioral verifier; then integrate and verify the full lifecycle | Critical |
| P-13 | Model-quality evaluation | Incomplete | No reliable evidence updates improved general coding accuracy | Establish baseline and broaden benchmark | Critical |
| P-14 | Integration into main | Incomplete | Features remain in stacked draft PRs | Verify dependencies and integrate safely | High |
| P-15 | Real-model resource benchmark | Pending | Inference deliberately avoided because prior RAM headroom was low | Recheck RAM before inference | Critical |
| P-16 | Restricted behavioral verifier | Implemented as an opt-in initial adapter; CI passed | Docker runner supports JSON-callable single-function cases; no Docker image is pulled; tests validate command safety, output limits, and runner syntax | Perform a controlled real-container smoke test with a preinstalled image; add broader trusted test interfaces only after isolation review | High |

### 1.1 Known pull-request stack

Statuses below reflect the audit snapshot and must be rechecked before integration.

| PR | Title | Known status | Main contents |
|---|---|---|---|
| [#1 — Read-only local Ollama model audit](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/1) | Model inventory | Draft, unmerged | Read-only inventory of local models |
| [#2 — Correction and syntax verification](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/2) | Correction foundation | Draft, unmerged | Bounded proposals and syntax validation |
| [#3 — Resource budget guard](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/3) | Resource safeguards | Draft, unmerged | RAM preflight and generation profiles |
| [#4 — Finite Ollama timeouts](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/4) | Timeout hardening | Draft, unmerged | Finite generation-timeout validation |
| [#5 — Deterministic coding smoke benchmark](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/5) | Initial benchmark | Draft, CI passed on recorded head | Three opt-in coding tasks |
| [#6 — Python AST validation](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/6) | Structural checks | Draft, CI passed on recorded head | AST checks for benchmark output |
| [#7 — Strict validation and audit timeouts](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/7) | Additional validation | Draft, CI passed on recorded head | Stricter AST checks and invalid/non-finite audit-timeout rejection |
| [#17 — Correction workflow coordinator](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/17) | Workflow and verifier slice | Draft; CI run #258 passed on Python 3.10–3.13; 121 tests in the Python 3.10 job | Strict proposal extraction, syntax gate, optional Docker verifier for JSON-callable functions, and provenance-aware ledger records; real Docker execution remains untested |

**Stack warning:** These PRs are stacked, not independent. Verify base/head relationships and combined diffs before merging. Do not merge a child PR into main while assuming its parent changes are already present.

## 2. Architecture review

| ID | File / component | Responsibility | Strength | Weakness / missing capability | Recommended improvement |
|---|---|---|---|---|---|
| A-01 | src/model_client.py | Communicates with local Ollama | Bounded requests, local endpoint, timeout controls | Successful response can still be incorrect | Add response validation, failure categories, integration tests |
| A-02 | src/resource_guard.py | Checks RAM and chooses inference settings | Resource-aware profiles and preflight | Preflight is a snapshot; cannot guarantee future/system-wide safety | Recheck before expensive work; measure usage |
| A-03 | src/task_router.py | Selects fast/balanced/deep profile | Lightweight heuristic | Heuristics are not evidence of better accuracy/efficiency | Compare routing to fixed profiles on same tasks |
| A-04 | src/error_analyzer.py | Classifies common errors | Gives correction prompts a starting point | Ambiguous/unseen errors may be misclassified | Expand taxonomy, tests, and unknown fallback |
| A-05 | src/self_corrector.py | Produces bounded proposals | Proposal-only behavior and limited attempts | Does not apply, test, or independently prove proposals | Connect to controlled verification lifecycle |
| A-06 | src/verification_runner.py | Parses Python and checks syntax | Does not execute candidate code | Syntax-valid code can behave incorrectly | Keep syntax as early gate; add restricted behavioral verification |
| A-07 | src/learning_ledger.py | Stores lesson/verification metadata | Append-only, bounded summaries, redaction; schema v2 stores source hash and verifier/run/check provenance | Ledger still cannot cryptographically prove evidence is genuine; retrieval learning incomplete | Require trusted verifier adapter and add provenance-aware retrieval |
| A-08 | src/model_audit.py | Inventories local Ollama models | Read-only; avoids downloads/generation | Inventory is not a performance ranking | Connect metadata to repeatable benchmark reports |
| A-09 | src/benchmark.py | Runs opt-in coding smoke tasks | Deterministic starting point; no inference unless explicitly requested | Three tasks too narrow for general claims | Expand tasks and evaluate behavior |
| A-10 | Integration/workflow layer | Should coordinate modules | Existing building blocks are reusable | No complete correction-to-verification-to-learning flow | Add explicit coordinator with bounded states |
| A-11 | Tests and CI | Exercises components across Python versions | Unit tests and multi-version CI | Does not prove end-to-end behavior or model quality | Add workflow tests and separate model evaluations |
| A-12 | Security boundaries | Restricts current correction behavior | Coordinator never applies candidate code; optional Docker adapter disables networking and limits resources | Container/kernel vulnerabilities and candidate/test interactions remain residual risks | Keep authorization and execution isolation outside model control |

**Architecture assessment:** The project is modular and safety-conscious. Its main weakness is the lack of integrated control flow and independent evidence for correctness. More prompts or model complexity before closing that gap could make the system more elaborate without making it more reliable.

## 3. Updates made and their strength on the model

| ID | Update | What changed | Strength added | Effect on underlying model intelligence | Remaining work |
|---|---|---|---|---|---|
| U-01 | Local Ollama client | Controlled communication with local model | Predictable inference interface | No direct weight change | Test failures and integration |
| U-02 | Bounded request handling | Limits prompt/response sizes | Reduces unbounded requests | Does not inherently improve correctness | Test truncation and limit behavior |
| U-03 | Timeout validation | Rejects invalid/excessive timeouts | Reduces certain hangs and invalid configs | No direct intelligence improvement | Keep regression tests |
| U-04 | RAM guard | Checks memory before inference | Avoids some low-headroom requests | No direct intelligence improvement | Measure resource effects |
| U-05 | Generation profiles | Fast, balanced, deep settings | Supports different resource budgets | May affect output quality, but benefit unmeasured | Compare profiles on identical tasks |
| U-06 | Task routing | Chooses profile using heuristics | Inexpensive task-aware orchestration | No demonstrated accuracy improvement | Measure routing against fixed profiles |
| U-07 | Error analysis | Classifies common failures | Can focus correction prompts | Correction benefit not demonstrated | Test classification and correction outcomes |
| U-08 | Self-correction | Bounded correction proposals | Adds controlled proposal stage | Does not establish fixes work | Add independent verification |
| U-09 | Syntax verification | Parses Python without execution | Rejects invalid syntax early | Improves validation, not model reasoning itself | Add behavioral tests |
| U-10 | Learning ledger | Stores compact lesson records | Infrastructure for future reuse | Does not retrain the model or guarantee better answers | Verified retrieval and evaluation |
| U-11 | Initial smoke benchmark | Three fixed tasks | Limited repeatable evaluation | Cannot establish general coding competence | Expand task coverage |
| U-12 | AST validation | Checks structure instead of only text markers | Rejects certain false positives | Raises confidence only for specific checks | Add behavioral tests and broader cases |
| U-13 | Strict AST validation | Rejects nested-return/extra-argument cases and filtered comprehensions where all items are required | Closes identified validation gaps | No direct model-weight change | Continue regression testing |
| U-14 | Audit-timeout hardening | Rejects NaN, infinity, non-positive, over-limit, and unrepresentably large values | Improves audit reliability | No direct intelligence improvement | Verify locally |

### What has genuinely improved

- **Reliability:** More bounded request behavior and stricter timeout validation.
- **Resource control:** Preflight and configurable inference budgets.
- **Correction discipline:** Bounded proposals rather than unrestricted automatic modification.
- **Validation:** Syntax and AST checks that reject specific malformed or misleading solutions.
- **Evaluation infrastructure:** A repeatable starting point for coding checks.

### What has not been demonstrated

- Better general coding accuracy or multi-step reasoning.
- Better real-project debugging.
- Better future answers from stored lessons.
- Lower measured RAM use at equivalent task quality.
- A superior installed model or routing strategy.

These require reproducible experiments. Orchestration changes should not be described as model-weight training or proven intelligence gains.

## 4. Full list of important missing capabilities

| ID | Missing capability | Why it matters | Required implementation | Priority | Dependency |
|---|---|---|---|---|---|
| M-01 | End-to-end correction workflow | Components do not yet form a complete verified process | Coordinator slice is in progress: proposal extraction, syntax gate, verifier handoff, ledger record; trusted behavioral runner remains missing | Critical | Core modules |
| M-02 | Behavioral verification | Correct syntax does not guarantee behavior | Initial Docker adapter tests JSON-callable functions in a restricted container; broader project tests remain unsupported | Critical | Verification architecture |
| M-03 | Independent verification evidence | Caller-supplied metadata alone is not proof | Coordinator checks candidate hash, configured verifier identity, run ID, and behavioral-test marker; real adapter must capture results from actual verification | Critical | Trusted verifier adapter |
| M-04 | Verified lesson retrieval | Stored lessons are not a complete learning mechanism | Retrieve relevant validated lessons with bounded context | Critical | Learning ledger |
| M-05 | Regression protection | Fix may solve one problem and break another | Run focused regression tests | Critical | Behavioral verification |
| M-06 | Broad coding benchmark | Three tasks cannot establish general coding ability | Add coding, debugging, edge-case, and refactoring tasks | Critical | Benchmark infrastructure |
| M-07 | Model comparison | Inventory cannot rank models | Evaluate candidates on identical tasks/settings | High | Expanded benchmark |
| M-08 | Prompt-injection resistance | Code/logs may contain misleading instructions | Treat code, logs, stack traces as untrusted data | Critical | Prompt/security controls |
| M-09 | Confidence/uncertainty handling | Model may claim more than evidence supports | Require uncertainty and evidence-backed claims | High | Prompts/response validation |
| M-10 | Multi-file reasoning evaluation | Real projects involve cross-file dependencies | Add related-module tasks | High | Expanded benchmark |
| M-11 | Failure recovery | Requests and outputs can fail | Test timeouts, malformed output, missing model, interrupted requests | High | Client/workflow |
| M-12 | Resource benchmarking | Savings are not measured | Record baseline/task-level RAM, CPU, latency | Critical | Safe benchmark runner |
| M-13 | Model-aware resource policy | Models have different memory needs | Use metadata and measurements to choose safe settings | High | Audit/resource guard |
| M-14 | Duplicate/contradictory lesson handling | Conflicting lessons can mislead future tasks | Deduplication, provenance, staleness/conflict handling | Medium | Learning ledger |
| M-15 | Safe execution isolation | Behavioral testing may execute candidate code | Initial Docker adapter uses no network, read-only mounts/root filesystem, resource limits, and no automatic image pull | Critical | Security design; real Docker validation still pending |
| M-16 | Reliable root-cause diagnosis | Wrong diagnosis causes unnecessary changes | Compare explanations with reproducible evidence | High | Analyzer/verifier |
| M-17 | Integration testing | Components may fail when combined | Test full workflow with controlled dependencies | Critical | Workflow coordinator |
| M-18 | Persistent evaluation history | Results are hard to compare over time | Compact, versioned reports | High | Benchmark reporting |
| M-19 | Change-scope validation | Fix may alter unrelated code | Compare changes against explicit allowed scope | High | Correction workflow |
| M-20 | Explicit approval boundaries | Future automation could perform risky actions | Require authorization; model output is never authorization | Critical | Security architecture |

**Recommended order:** M-01–M-05, then M-08 and M-15, then M-06 and M-12. Prioritize correctness and safety before more automation or model comparisons.

## 5. Full engineering gaps

| ID | Engineering gap | Current risk | Recommended task | Completion criteria |
|---|---|---|---|---|
| E-01 | Missing workflow integration | No complete verification lifecycle yet | Implemented first coordinator slice in workflow branch | Proposal extraction, syntax gate, bounded outcomes, and ledger status are tested; trusted behavioral adapter remains outstanding |
| E-02 | Limited benchmark coverage | Results may overstate coding ability | Expand task suite | Diverse tasks and deliberately incorrect candidates |
| E-03 | No end-to-end behavioral verification | Syntax-valid fix may be wrong | Added opt-in Docker function verifier with JSON input/expected-output cases | Mocked tests cover command safety and evidence parsing; actual container execution and general project tests remain unverified |
| E-04 | Caller-supplied verification claims | Ledger status may mislead | Require matching source hash, verifier identity, run ID, and behavioral-check provenance | Coordinator checks the evidence shape; real adapter must generate trustworthy results |
| E-05 | Prompt-injection exposure | Untrusted input can influence instructions | Strengthen boundaries and add adversarial tests | Input text cannot authorize actions |
| E-06 | No resource baseline | Efficiency claims unsupported | Measure resource use | Baseline, workload, RAM, CPU, latency recorded |
| E-07 | Unvalidated routing heuristics | Routing may waste resources/reduce quality | Benchmark routing | Compare routed strategy to fixed profiles |
| E-08 | Limited model-selection evidence | Model choice not evidence-based | Reproducible comparisons | Model/version/settings/scores reported |
| E-09 | Incomplete error taxonomy | Unknown errors may be misdiagnosed | Expand tests and fallback | Unknown errors remain explicitly unknown |
| E-10 | Limited integration coverage | Module interactions may break | Workflow integration tests | Major success/failure paths covered |
| E-11 | Limited static quality gates | Unit tests miss style/maintainability issues | Evaluate Ruff and static checks in CI | New changes pass agreed gates |
| E-12 | No system-wide resource coordination | Other processes can consume RAM after preflight | Recheck before expensive work | Low-memory scenarios tested |
| E-13 | Resource overrides can increase usage | Overrides may exceed conservative defaults | Validate resolved settings | Effective settings visible; invalid values rejected |
| E-14 | Incomplete learning lifecycle | Stale/conflicting lessons may mislead | Add versioning, provenance, retrieval controls | Retrieved lessons have source and status |
| E-15 | Limited observability | Failures hard to diagnose | Structured privacy-conscious diagnostics | Failures categorized without sensitive leaks |
| E-16 | Stacked PR management | Changes may use incomplete parent branches | Verify dependency chain | Each PR checked against intended base |
| E-17 | Local verification outstanding | CI does not confirm laptop behavior | Test latest branch locally | Tests pass and working-tree status inspected |
| E-18 | Incomplete failure recovery | Failures may leave ambiguous state | Deterministic failure states | Every failure yields bounded understandable outcome |
| E-19 | No proof of accuracy improvement | Engineering changes mistaken for intelligence gains | Establish baseline and compare | Reproducible measurements show change |
| E-20 | No end-to-end latency budget | Correction loops may be slow | Set/test total workflow budget | Documented overall time limit respected |

## 6. What is actually in progress?

| ID | Task | Status | Latest known evidence | Remaining action |
|---|---|---|---|---|
| W-01 | Read-only model audit | Draft PR #1 | Unmerged in recorded audit | Verify and integrate |
| W-02 | Correction and syntax verification | Draft PR #2 | Unmerged in recorded audit | Verify dependencies and integrate |
| W-03 | Resource budget guard | Draft PR #3 | Unmerged in recorded audit | Validate and measure resource use |
| W-04 | Generation timeout hardening | Draft PR #4 | Unmerged in recorded audit | Verify and integrate |
| W-05 | Initial coding benchmark | Draft PR #5 | CI passed on recorded head | Expand tasks |
| W-06 | AST validation | Draft PR #6 | CI passed on recorded head | Verify latest branch and expand checks |
| W-07 | Strict AST/audit-timeout validation | Draft PR #7 | CI passed on recorded head | Run local tests and inspect status |
| W-08 | Correction-to-verification integration | In progress in draft PR #17; CI passed on Python 3.10–3.13 | Coordinator connects correction proposal, strict source extraction, syntax validation, optional trusted-verifier handoff, and ledger recording | Add a real restricted behavioral verifier; then run full integration checks |
| W-09 | Evidence-backed learning | Partially implemented on workflow branch | Ledger schema v2 records source hash, verifier ID, run ID, and behavioral-check names; coordinator gates VERIFIED on matching adapter evidence | Build and test a trusted adapter; preserve the direct-API trust caveat |
| W-10 | Behavioral benchmark | Planned | Current benchmark is smoke test | Build broader suite |
| W-11 | Real-model resource measurement | Pending | No recent inference result established | Recheck RAM |
| W-12 | Model accuracy comparison | Pending | No comparable results | Benchmark under controlled settings |
| W-13 | Prompt-injection hardening | Incomplete | Boundaries need more work | Add defenses and regression tests |
| W-14 | Safe behavioral-test isolation | Not implemented end to end | Syntax check does not execute code | Design restricted execution |
| W-15 | Main-branch integration | Pending | PR stack unmerged in recorded audit | Integrate after review |
| W-17 | Docker behavioral verifier | Implemented; CI run #279 passed | No-pull image check, network-disabled container, read-only mount/root filesystem, resource limits, isolated per-case child process, strict result summary, bounded host output, and extreme-timeout rejection | Run the owner-invoked smoke helper on Windows/Docker Desktop; broader project-level test interfaces remain future work | 
| W-18 | Real Docker smoke test | Helper implemented; owner-run validation pending | `scripts/docker_verifier_smoke.py` requires explicit `--run`, blocks below 1536 MiB or unknown RAM, and uses only an already-installed image | First run `python -m scripts.docker_verifier_smoke` for help; then run with `--run` only when Docker/image/free-RAM preflight is satisfied |
| W-19 | Cross-component workflow integration | CI run #279 passed | Test wires `CorrectionWorkflow`, `DockerFunctionVerifier`, and schema-v2 ledger with mocked Docker boundary; real container is not run | Validate one real Docker smoke test separately; keep general multi-file test execution as a separate future milestone |
| W-16 | Workflow coordinator verification | Coordinator and optional adapter implemented; CI run #279 passed | Run #279 passed on Python 3.10–3.13; Python 3.10 ran 126 tests | Continue with a real Docker smoke test and broader project-level verification; do not merge stacked PRs yet |

### Current blockers

1. PR #7 needs local testing.
2. There is no complete correction-to-verification pipeline.
3. Three smoke tasks are insufficient for model comparisons.
4. Real inference needs a fresh RAM check.
5. The opt-in `scripts/docker_verifier_smoke.py` helper now provides a fixed
three-case test and refuses to run without `--run` or at least 1536 MiB free
RAM. It uses only an image already present locally. The real Windows/Docker
Desktop smoke test still needs to be run by the owner; CI continues to mock Docker.
6. The stacked PRs need dependency review before merging.

## 7. Main architectural limitations and strength of updates

| ID | Limitation | Current situation | Strength of updates | Remaining weakness | Best next improvement |
|---|---|---|---|---|---|
| L-01 | Model correctness | Responses can be wrong | Bounded correction and validation infrastructure | No complete behavioral verification | Independent tests |
| L-02 | Reasoning quality | Prompts request evidence/edge cases | Better instructions and routing | No demonstrated accuracy gain | Representative task comparison |
| L-03 | Learning | Lessons can be stored | Append-only ledger/summaries | No verified retrieval cycle | Feed verified outcomes into future tasks |
| L-04 | Resource efficiency | Profiles and RAM checks exist | Bounded settings/preflight | Savings unmeasured | Controlled resource benchmark |
| L-05 | Model selection | Models can be inventoried | Read-only audit | No coding-performance ranking | Identical-task comparisons |
| L-06 | Verification | Syntax and AST checks exist | Stronger than marker-only checks | Does not prove behavior | Restricted behavioral testing |
| L-07 | Security | Correction is proposal-only | Avoids automatic changes/execution in current flow | Future integrations may introduce risk | Independent authorization/isolation |
| L-08 | Prompt injection | Model receives code/diagnostics | Bounded prompts provide some structure | Untrusted text can influence model | Explicit separation/adversarial tests |
| L-09 | Multi-file debugging | Modules support coding tasks | Modular foundation | End-to-end capability unproven | Multi-file regression tasks |
| L-10 | Self-improvement | Corrections can be recorded | Infrastructure exists | No demonstrated benefit from records | Compare against baseline |
| L-11 | Reliability | Unit tests and CI exist | Multi-version testing | Integration/model failures not fully covered | Workflow failure tests |
| L-12 | Observability | Some errors/outcomes recorded | Diagnostic and ledger foundations | No unified evidence report | Structured workflow reports |
| L-13 | Generalization | Three narrow tasks | Repeatable checks | Not representative of coding work | Broader benchmark |
| L-14 | Integration readiness | Features exist across branches | Scoped review possible | Not all features in main | Verify/integrate PR stack safely |

## 8. Dependency-ordered development roadmap

| Phase | Task | Deliverable | Exit criteria | Priority |
|---|---|---|---|---|
| 1 | Verify latest PR #7 locally | Test/status report | Tests pass; repository state understood | Immediate |
| 2 | Audit stacked PR dependencies | Integration plan | No missing dependency or accidental overwrite | Immediate |
| 3 | Design correction workflow | Coordinator slice in workflow branch | Proposal parsing, syntax gate, bounded failure states, and no-auto-apply boundary are implemented; behavioral runner contract still needs a trusted adapter | Critical |
| 4 | Integrate correction and syntax validation | Proposal-validation coordinator | Strictly extract one replacement block, reject ambiguous output, and keep candidate code unexecuted | Critical |
| 5 | Add independent verification evidence | Source-bound verifier handoff and ledger provenance | Coordinator checks source hash and verifier identity; completion still requires a real trusted adapter that generates evidence | Critical |
| 6 | Add controlled behavioral testing | Initial Docker function verifier; CI suite green | JSON-callable function candidates pass/fail trusted expected-output cases; real container execution and general project tests remain future work | Critical |
| 7 | Integrate learning ledger | Coordinator writes UNVERIFIED/SYNTAX_VALID or gated VERIFIED records | Tests show only matching successful adapter evidence can promote a record; actual adapter trust/isolation remains outstanding | Critical |
| 8 | Harden untrusted-input handling | Adversarial regression tests | Untrusted content cannot authorize actions | Critical |
| 9 | Expand coding benchmark | Behavioral benchmark | Diverse tasks cover common failures | Critical |
| 10 | Measure RAM and latency | Resource report | Baseline/task-level usage recorded | Critical |
| 11 | Evaluate routing | Routing comparison | Routing compared with fixed profiles | High |
| 12 | Compare installed models | Model evaluation report | Same tasks/comparable settings | High |
| 13 | Expand multi-file debugging | Multi-file suite | Cross-module failures covered | High |
| 14 | Improve diagnostics | Structured privacy-conscious reports | Failures explainable without leaks | High |
| 15 | Integrate reviewed PRs | Safe main-branch integration | Dependencies/tests verified | High |
| 16 | Evaluate verified learning | Before/after evaluation | Improvement demonstrated on held-out tasks | High |

## 9. Laptop/resource constraints and benchmark safety

The target machine has 8 GB RAM. Earlier context recorded low available-memory headroom, but that is not a current measurement.

| Constraint | Current policy / known behavior | Required care |
|---|---|---|
| Low available RAM | Resource guard has a 1536 MiB minimum threshold | Recheck immediately before inference |
| Deep profile | Reduced to balanced if RAM is unknown or below 2048 MiB | Do not assume deep mode is safe |
| Model downloads | Audit/smoke checks do not require downloads | Do not download large weights without explicit need/approval |
| Benchmark execution | No inference unless explicitly opted in with run flag | Preserve opt-in behavior |
| Generated code | Coordinator does not execute candidates; optional Docker adapter executes only inside a constrained, network-disabled container | No real container run claimed; adapter tests currently mock Docker |
| Resource claims | No equivalent-workload measurements prove savings | Report measurements, not assumptions |
| Ollama concurrency | Lock serializes requests within one Python process | Does not coordinate other apps/processes |

## 10. Definition of done for major milestones

| Milestone | Acceptance criteria |
|---|---|
| Correction workflow | Explicit states, bounded retries, deterministic failure handling |
| Syntax validation | Malformed Python rejected; valid syntax not assumed correct |
| Behavioral verification | Trusted tests run in restricted environment; actual results captured |
| Learning ledger integration | Records linked to source hashes and actual verification; unverified proposals are not promoted |
| Benchmark | Reproducible task/model/settings/outcome report with limitations |
| Resource benchmark | Baseline and workload-specific RAM/CPU/latency recorded |
| Model comparison | Same tasks and comparable settings; trade-offs reported |
| Security boundary | Model text cannot authorize execution, file modification, or privileged actions |
| PR integration | Correct parents, combined diffs, tests, and CI verified; no safety gate bypassed |
| Accuracy claim | Improvement demonstrated against baseline on representative, preferably held-out tasks |

## Final recommendation

The highest-value milestone remains the **correction → independent verification → evidence-backed learning workflow**. The first coordinator slice is being implemented on the workflow branch: it connects proposal extraction, syntax checks, a source-bound trusted-verifier contract, and ledger provenance. It is not complete until a real restricted behavioral verifier is implemented and independently tested.

Priorities:
1. Correctness before autonomy.
2. Measured results before claims of improvement.
3. Verified learning before automatic learning.
4. Resource measurements before heavier models or longer inference.
5. Safe integration before merging stacked draft PRs.

Do not describe the project as having improved model intelligence, coding accuracy, or RAM efficiency until repeatable measurements support those claims. Keep the task table updated as each remaining workflow milestone gains fresh verification evidence.
