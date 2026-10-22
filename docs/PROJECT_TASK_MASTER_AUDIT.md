# Jarvis Coding Intelligence — Full Project Task Master Audit

**Repository:** SHAZAM-1/jarvis-coding-intelligence  
**Audit date:** 2026-10-22  
**Scope:** Current status, architecture, updates, model impact, missing capabilities, engineering gaps, active work, architectural limitations, and roadmap.

> **Evidence policy:** This document distinguishes implemented code, CI evidence, local verification, measured outcomes, and planned work. Passing unit tests does not prove coding accuracy. Prompting, routing, validation, and workflow improvements do not themselves change model weights. Do not claim accuracy gains or RAM savings without reproducible measurements.

## Executive summary

Jarvis has a useful modular foundation: local Ollama client, resource guard, heuristic task router, error analyzer, bounded correction proposals, non-executing Python syntax checks, learning ledger, model inventory, and opt-in coding smoke benchmark.

The main limitation is **behavioral verification and evidence**. A first end-to-end slice now connects a bounded proposal, single-candidate extraction, non-executing syntax verification, and conservative ledger recording. It deliberately does not execute or apply candidate code, and it does not claim behavioral correctness. The three-task benchmark remains a smoke check, not a general coding-ability measure.

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
| P-08 | Learning ledger | Receipt-gated VERIFIED path and conservative retrieval implemented on feature branch | Append-only records, bounded summaries, redaction; direct status assignment and caller-supplied evidence rejected | Validate real sandbox integration; later evaluate semantic retrieval | Critical |
| P-09 | Coding smoke benchmark | Implemented in draft PR | Three fixed tasks; narrow coverage | Expand into behavioral benchmark | Critical |
| P-10 | AST validation | Implemented in draft PR | Checks structure for built-in benchmark tasks | Verify locally; extend regression coverage | High |
| P-11 | Strict AST/audit-timeout checks | Implemented in PR #7 | GitHub Actions passed on recorded head; local verification still outstanding in latest known status | Run local tests and inspect Git status | High |
| P-12 | Correction-to-ledger workflow | Proposal/syntax flow plus explicit behavioral-verification method implemented; CI run #185 passed 127 tests on Python 3.10–3.13 | Normal run remains non-executing; separate method requires allow_execution=True and a configured Docker verifier | Verify integration CI; real Docker/local tests remain pending | Critical |
| P-13 | Model-quality evaluation | Incomplete | No reliable evidence updates improved general coding accuracy | Establish baseline and broaden benchmark | Critical |
| P-14 | Integration into main | Incomplete | Features remain in stacked draft PRs | Verify dependencies and integrate safely | High |
| P-15 | Real-model resource benchmark | Pending | Inference deliberately avoided because prior RAM headroom was low | Recheck RAM before inference | Critical |
| P-16 | Docker behavioral verifier | Implemented on feature branch in draft PR #11; CI run #167 passed 121 tests on Python 3.10–3.13; real Docker run pending | Opt-in Docker-only runner, pinned image digest, JSON test cases, bounded output/timeout, host-side expected-output comparison, typed receipt | Run CI, inspect command/safety tests, then opt-in real-Docker test only with preloaded image and fresh RAM preflight | Critical |

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
| [#8 — Full project task master audit](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/8) | Project audit document | Draft, unmerged | Full task/status tables and dependency-ordered roadmap |
| [#9 — Correction workflow and evidence policy](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/9) | Initial correction-to-ledger workflow | Draft PR open; CI runs #115 and #117 passed (102 tests on Python 3.10–3.13) | Connects proposal, syntax verification, and conservative learning records; no candidate execution |
| [#10 — Fail-closed behavioral verification design](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/10) | Behavioral verifier design | Draft PR open; CI run #122 passed 102 tests | Defines Docker-only, opt-in, no-image-pull execution policy and evidence requirements |
| [#11 — Docker behavioral verifier](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/11) | Initial isolated behavioral verifier | Draft PR #11 open; CI run #167 passed 121 tests on Python 3.10–3.13; no real Docker run | Runs JSON-compatible callable cases only in a pinned, preloaded Docker image; no host fallback or automatic pull |
| [#12 — Explicit opt-in behavioral workflow](https://github.com/SHAZAM-1/jarvis-coding-intelligence/pull/12) | Correction workflow integration | Draft PR open; CI run #185 passed 127 tests on Python 3.10–3.13 | Normal correction stays syntax-only; separate behavioral stage requires explicit opt-in and receipt-gated learning |

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
| A-07 | src/learning_ledger.py | Stores lesson and verifier-receipt metadata | Append-only, bounded summaries, redaction, source-hash-bound receipts | Real Docker integration not verified; retrieval learning incomplete | Validate receipts with opt-in sandbox runs; add provenance-aware retrieval |
| A-08 | src/model_audit.py | Inventories local Ollama models | Read-only; avoids downloads/generation | Inventory is not a performance ranking | Connect metadata to repeatable benchmark reports |
| A-09 | src/benchmark.py | Runs opt-in coding smoke tasks | Deterministic starting point; no inference unless explicitly requested | Three tasks too narrow for general claims | Expand tasks and evaluate behavior |
| A-10 | Integration/workflow layer | Should coordinate modules | Existing building blocks are reusable | No complete correction-to-verification-to-learning flow | Add explicit coordinator with bounded states |
| A-11 | Tests and CI | Exercises components across Python versions | Unit tests and multi-version CI | Does not prove end-to-end behavior or model quality | Add workflow tests and separate model evaluations |
| A-12 | Security boundaries | Restricts current correction behavior | No automatic file changes or generated-code execution in current flow | Future execution features could weaken safety | Keep authorization and execution isolation outside model control |

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
| M-01 | Full behavioral correction workflow | Initial syntax-only slice now connects proposal, candidate parsing, and ledger recording | Add trusted, isolated behavioral verification and regression checks | Critical | Core modules and safe execution isolation |
| M-02 | Behavioral verification | Correct syntax does not guarantee behavior | Run trusted tests in controlled environment | Critical | Verification architecture |
| M-03 | Independent behavioral verification evidence | Ledger blocks direct SYNTAX_VALID/VERIFIED claims and independently parses before SYNTAX_VALID; behavioral evidence is still missing | Capture test results from a trusted verifier that actually ran them | Critical | Verification runner and execution isolation |
| M-04 | Verified lesson retrieval | Initial bounded retrieval implemented on feature branch | Retrieve recent structurally valid VERIFIED records by category/limit; no semantic ranking yet | High | Learning ledger |
| M-05 | Regression protection | Fix may solve one problem and break another | Run focused regression tests | Critical | Behavioral verification |
| M-06 | Broad coding benchmark | Three tasks cannot establish general coding ability | Add coding, debugging, edge-case, and refactoring tasks | Critical | Benchmark infrastructure |
| M-07 | Model comparison | Inventory cannot rank models | Evaluate candidates on identical tasks/settings | High | Expanded benchmark |
| M-08 | Prompt-injection resistance | Initial defense-in-depth update added on feature branch | Task, source, failure output, and analyzer excerpts serialized into one JSON untrusted-data object; model output still not authority | Critical | Continue adversarial testing; never treat delimiters as a sandbox |
| M-09 | Confidence/uncertainty handling | Model may claim more than evidence supports | Require uncertainty and evidence-backed claims | High | Prompts/response validation |
| M-10 | Multi-file reasoning evaluation | Real projects involve cross-file dependencies | Add related-module tasks | High | Expanded benchmark |
| M-11 | Failure recovery | Requests and outputs can fail | Test timeouts, malformed output, missing model, interrupted requests | High | Client/workflow |
| M-12 | Resource benchmarking | Savings are not measured | Record baseline/task-level RAM, CPU, latency | Critical | Safe benchmark runner |
| M-13 | Model-aware resource policy | Models have different memory needs | Use metadata and measurements to choose safe settings | High | Audit/resource guard |
| M-14 | Duplicate/contradictory lesson handling | Conflicting lessons can mislead future tasks | Deduplication, provenance, staleness/conflict handling | Medium | Learning ledger |
| M-15 | Safe execution isolation | Behavioral testing may execute candidate code | Restricted execution, explicit limits, no inherited secrets | Critical | Security design |
| M-16 | Reliable root-cause diagnosis | Wrong diagnosis causes unnecessary changes | Compare explanations with reproducible evidence | High | Analyzer/verifier |
| M-17 | Integration testing | Components may fail when combined | Test full workflow with controlled dependencies | Critical | Workflow coordinator |
| M-18 | Persistent evaluation history | Results are hard to compare over time | Compact, versioned reports | High | Benchmark reporting |
| M-19 | Change-scope validation | Fix may alter unrelated code | Compare changes against explicit allowed scope | High | Correction workflow |
| M-20 | Explicit approval boundaries | Future automation could perform risky actions | Require authorization; model output is never authorization | Critical | Security architecture |

**Recommended order:** M-01–M-05, then M-08 and M-15, then M-06 and M-12. Prioritize correctness and safety before more automation or model comparisons.

## 5. Full engineering gaps

| ID | Engineering gap | Current risk | Recommended task | Completion criteria |
|---|---|---|---|---|
| E-01 | Missing workflow integration | No complete verification lifecycle | Build workflow coordinator | Explicit stages/states from proposal through result |
| E-02 | Limited benchmark coverage | Results may overstate coding ability | Expand task suite | Diverse tasks and deliberately incorrect candidates |
| E-03 | No end-to-end behavioral verification | Syntax-valid fix may be wrong | Implement controlled tests | Incorrect candidates fail relevant tests |
| E-04 | Caller-supplied verification claims | Hardened: public writes cannot claim SYNTAX_VALID/VERIFIED or attach evidence; a dedicated method reparses source; behavioral evidence still missing | Add trusted behavioral verifier and evidence receipt | Only verifier-produced results can support VERIFIED |
| E-05 | Prompt-injection exposure | Structured JSON boundary and explicit distrust instructions added; model susceptibility cannot be eliminated by prompt text alone | Add adversarial prompt-injection regression suite and keep authorization outside model | Tests preserve untrusted input as JSON data; no tool/action authority is delegated |
| E-06 | No resource baseline | Efficiency claims unsupported | Measure resource use | Baseline, workload, RAM, CPU, latency recorded |
| E-07 | Unvalidated routing heuristics | Routing may waste resources/reduce quality | Benchmark routing | Compare routed strategy to fixed profiles |
| E-08 | Limited model-selection evidence | Model choice not evidence-based | Reproducible comparisons | Model/version/settings/scores reported |
| E-09 | Incomplete error taxonomy | Unknown errors may be misdiagnosed | Expand tests and fallback | Unknown errors remain explicitly unknown |
| E-10 | Limited integration coverage | Module interactions may break | Workflow integration tests | Major success/failure paths covered |
| E-11 | Limited static quality gates | Unit tests miss style/maintainability issues | Evaluate Ruff and static checks in CI | New changes pass agreed gates |
| E-12 | No system-wide resource coordination | Other processes can consume RAM after preflight | Recheck before expensive work | Low-memory scenarios tested |
| E-13 | Resource overrides can increase usage | Overrides may exceed conservative defaults | Validate resolved settings | Effective settings visible; invalid values rejected |
| E-14 | Incomplete learning lifecycle | Basic receipt/schema-checked retrieval added; ledger is still editable and non-tamper-proof | Add versioning, provenance, staleness/conflict controls, and retrieval evaluation | Retrieved lessons expose source hash/status and compact receipt; malformed entries are ignored |
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
| W-08 | Correction-to-ledger workflow | Draft PR #9: proposal/syntax slice passed CI; PR #12 explicit behavioral method passed CI | Normal run never invokes behavioral execution; verify_behavior requires explicit opt-in | Verify PR #12 CI and inspect integration diff; real Docker run remains pending |
| W-09 | Evidence-backed learning | Partial: receipt-gated records and bounded VERIFIED retrieval implemented; real Docker run pending | Candidate hash bound to receipt; caller-supplied status/evidence rejected; malformed stored entries filtered | Run opt-in sandbox integration and evaluate retrieval impact on future tasks |
| W-10 | Behavioral benchmark | Planned | Current benchmark is smoke test | Build broader suite |
| W-11 | Real-model resource measurement | Pending | No recent inference result established | Recheck RAM |
| W-12 | Model accuracy comparison | Pending | No comparable results | Benchmark under controlled settings |
| W-13 | Prompt-injection hardening | Incomplete | Boundaries need more work | Add defenses and regression tests |
| W-14 | Safe behavioral-test isolation | Runner implemented in draft PR #11; CI run #167 passed 121 tests; no real Docker run | Docker-only, opt-in, no-pull design for declarative JSON cases; unit tests use a fake process | Verify CI, then review opt-in integration on a preloaded image |
| W-16 | Receipt-gated VERIFIED ledger | Verifier unit suite passed CI; workflow integration pending CI | Public status assignment blocked; ledger requires verifier-issued receipt bound to source hash | Keep real Docker integration pending |
| W-15 | Main-branch integration | Pending | PR stack unmerged in recorded audit | Integrate after review |

### Current blockers

1. PR #7 needs local testing.
2. There is no complete correction-to-verification pipeline.
3. Three smoke tasks are insufficient for model comparisons.
4. Real inference needs a fresh RAM check.
5. The stacked PRs need dependency review before merging.

## 7. Main architectural limitations and strength of updates

| ID | Limitation | Current situation | Strength of updates | Remaining weakness | Best next improvement |
|---|---|---|---|---|---|
| L-01 | Model correctness | Responses can be wrong | Bounded correction and validation infrastructure | No complete behavioral verification | Independent tests |
| L-02 | Reasoning quality | Prompts request evidence/edge cases | Better instructions and routing | No demonstrated accuracy gain | Representative task comparison |
| L-03 | Learning | Syntax records, receipt-gated VERIFIED writes, and bounded VERIFIED retrieval implemented | Append-only ledger, source-hash binding, verifier-issued receipt, schema-checked retrieval | Real Docker integration untested; no semantic retrieval or measured future-task benefit | Add provenance-aware semantic retrieval only after baseline evaluation |
| L-04 | Resource efficiency | Profiles and RAM checks exist | Bounded settings/preflight | Savings unmeasured | Controlled resource benchmark |
| L-05 | Model selection | Models can be inventoried | Read-only audit | No coding-performance ranking | Identical-task comparisons |
| L-06 | Verification | Syntax and AST checks exist | Stronger than marker-only checks | Does not prove behavior | Restricted behavioral testing |
| L-07 | Security | Correction is proposal-only | Avoids automatic changes/execution in current flow | Future integrations may introduce risk | Independent authorization/isolation |
| L-08 | Prompt injection | Inputs now serialized as one JSON payload marked untrusted | Clear trust boundary and no authority delegation | Defense-in-depth only; adversarial robustness is not proven | Expand injection tests and keep all privileged actions outside model control |
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
| 3 | Design correction workflow | Workflow specification | States, failure paths, approval boundaries defined | Critical |
| 4 | Integrate correction and syntax validation | Proposal-validation pipeline | Invalid proposals rejected; no auto-execution | Critical |
| 5 | Add independent verification evidence | Evidence tied to source hashes | Status reflects actual verification | Critical |
| 6 | Add controlled behavioral testing | Restricted test runner | Candidates pass/fail trusted tests | Critical |
| 7 | Integrate learning ledger | Evidence-backed learning pipeline | Only appropriately verified outcomes become trusted lessons | Critical |
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
| Generated code | Current syntax checks do not execute generated code | Keep execution disabled until isolation reviewed |
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

## 11. Implementation update — 2026-10-22

| ID | Task-table item | Change now made | Evidence status | Next gate |
|---|---|---|---|---|
| IMP-01 | Correction workflow | Added `src/correction_workflow.py` to connect the existing corrector, strict single-fenced-Python extraction, syntax parsing, and ledger recording | Source and safety-policy docs committed to feature branch; CI run #115 passed on commit fa6533e (102 tests across Python 3.10–3.13) | Run focused and full unit tests in CI |
| IMP-02 | Candidate output contract | Updated the correction prompt to request exactly one fenced Python candidate | Source change committed; behavior not yet independently tested on a real model | Unit-test prompt contract; avoid inference until RAM preflight |
| IMP-03 | Evidence honesty | Ledger independently parses source before SYNTAX_VALID and rejects caller-supplied status/evidence | Regression tests updated; CI passed across Python 3.10–3.13 | Confirm tests pass and no call sites depend on caller-supplied VERIFIED |
| IMP-04 | Syntax-only evidence | Syntax-valid candidate is recorded as SYNTAX_VALID with candidate SHA-256; malformed/missing candidates stay UNVERIFIED | Focused tests added; CI passed across Python 3.10–3.13 | Verify hash, status, and privacy behavior |
| IMP-05 | Execution safety | Workflow explicitly does not apply or execute proposed code | Covered by API flags and tests; CI passed across Python 3.10–3.13 | Keep behavioral execution out until isolation design is reviewed |
| IMP-06 | Behavioral verification | Not implemented yet | No behavioral correctness claim is made | Design restricted runner with clear platform limits and no inherited secrets |
| IMP-07 | Task table maintenance | Status rows and roadmap updated to reflect partial implementation | CI runs #115/#117 passed for PR #9's 102-test suite | Continue updating after design review and implementation gates |

**Current phase result: PARTIAL.** The proposal → syntax check → conservative ledger slice and aligned safety documentation passed CI run #115 (102 tests across Python 3.10–3.13). The latest task-table-only edit is documentation; it is not merged or locally verified, and the workflow is not behaviorally verified. Do not label a candidate as a verified fix.

## 12. Behavioral verification design — 2026-10-22

| ID | Task-table item | Current state | Safety boundary | Next gate |
|---|---|---|---|---|
| BV-01 | Threat model and supported scope | Documented in draft PR #10 | First version covers single-callable Python with JSON-compatible inputs/outputs, not arbitrary project commands | Review scope before code |
| BV-02 | Sandbox backend | Design only | Docker required; no host fallback and no automatic image pull | Implement fail-closed Docker/image preflight |
| BV-03 | Candidate/test separation | Design only | Expected values stay in host controller; candidate receives inputs only | Implement worker protocol and malformed-output rejection |
| BV-04 | Resource limits and timeout cleanup | Design only | Non-root, network-disabled, read-only container with bounded resources | Unit-test exact runtime arguments and cleanup |
| BV-05 | Evidence receipt | Design only | Candidate cannot supply its own success state or expected results | Bind result to source hash, manifest hash, image digest, case counts, and verifier outcome |
| BV-06 | VERIFIED ledger status | Intentionally disabled | Syntax-only status cannot imply behavioral correctness | Re-enable only after trusted verifier receipt contract is implemented and tested |
| BV-07 | Runtime execution | Not performed | No Docker invocation, candidate execution, model inference, or image download in this phase | Only opt-in integration tests with an already-present pinned image |
| BV-08 | Laptop resource assessment | Pending | 8 GB RAM; Docker host overhead is not yet measured | Fresh RAM preflight and explicit approval before integration execution |

**Phase result: DESIGN READY FOR REVIEW, NOT IMPLEMENTED.** The design intentionally narrows the first behavioral verifier to JSON-compatible callable tests. It does not authorize arbitrary shell commands or direct host execution. The existing syntax-only workflow and VERIFIED lock remain in place.

## 13. Behavioral verifier implementation — 2026-10-22

| ID | Task-table item | Change now made | Evidence status | Next gate |
|---|---|---|---|---|
| BV-10 | Docker-only runner | Added an opt-in verifier that requires an immutable image digest and verifies the image is already local | CI run #167 passed 121 tests across Python 3.10–3.13; tests use a fake process and no Docker daemon was invoked | Independent code review and opt-in integration later |
| BV-11 | Host-held expected outputs | Only args/kwargs are sent to the worker; expected values stay in the host controller | Unit test inspects the submitted JSON input | Add adversarial protocol tests and inspect the final diff |
| BV-12 | Container restrictions | Network disabled, read-only root/workspace, non-root user, dropped capabilities, resource caps, no-new-privileges, no automatic image pull | Command-construction unit tests passed in CI; actual Docker behavior unverified | Run opt-in integration tests only with a preloaded pinned image |
| BV-13 | Timeout/output limits | Bounded stdout/stderr, total timeout, explicit container cleanup request | Mocked timeout/overflow tests added; CI pending | Confirm latest CI and cleanup-failure behavior |
| BV-14 | Evidence receipt | Receipt binds source hash, manifest hash, image digest, policy, counts, exit status, duration, and timestamp | Typed receipt is only trusted when issued by verifier implementation; CI passed | Keep receipt forgery, mismatch, and failed-case rejection covered |
| BV-15 | Ledger promotion | Added receipt-gated VERIFIED method; direct status assignment remains rejected | Unit test covers successful receipt and failed receipt rejection; CI pending | Review API and keep VERIFIED gated if any concern remains |
| BV-16 | Real sandbox validation | Not performed | No Docker invocation, image pull, or candidate execution by this assistant | Requires a fresh RAM check and opt-in test on a machine with the approved image already present |

**Current phase result: IMPLEMENTATION IN PROGRESS.** The runner is designed to fail closed and does not automatically execute during normal correction. The code and tests passed CI run #155 (121 tests across Python 3.10–3.13). A real Docker integration run and Windows resource measurement remain separate, unverified steps.

## 14. Explicit behavioral-verification integration — 2026-10-22

| ID | Task-table item | Change now made | Evidence status | Next gate |
|---|---|---|---|---|
| INT-01 | Separate opt-in API | Added CorrectionWorkflow.verify_behavior with allow_execution defaulting to false | Focused unit tests added; CI run #185 passed 127 tests | Confirm normal run never calls the verifier |
| INT-02 | Receipt-gated success | Successful verifier result routes through LearningLedger.append_verified_record | Orchestration test added; receipt validation is separately covered in verifier tests; CI passed | Run full CI and inspect source-hash binding |
| INT-03 | Failed behavioral result | Failed cases are recorded only as UNVERIFIED; no VERIFIED promotion | Focused test added; CI passed | Confirm failure status and compact summary |
| INT-04 | No silent execution | Normal CorrectionWorkflow.run does not call the behavioral verifier even when configured | Regression test added; CI passed | Keep this invariant in future refactors |
| INT-05 | Runtime execution | Not performed | No Docker daemon, candidate execution, image pull, or model inference performed | Opt-in integration requires preloaded pinned image and fresh RAM preflight |

**Current phase result: INTEGRATION IMPLEMENTED, CI VERIFIED, REAL SANDBOX UNVERIFIED.** PR #12 passed 127 unit tests across Python 3.10–3.13. The normal correction path remains non-executing. Behavioral checks require a separately configured verifier and explicit opt-in; successful evidence can be recorded only through the receipt-checked ledger method. No real Docker integration run or Windows resource measurement has been performed.

## 15. Conservative verified-lesson retrieval — 2026-10-22

| ID | Task-table item | Change now made | Evidence status | Next gate |
|---|---|---|---|---|
| LR-01 | Bounded ledger scan | Added a bounded file-size limit, bounded line length, and recent-record tail | Unit tests added; CI pending | Confirm malformed/oversized entries fail closed |
| LR-02 | VERIFIED-only retrieval | Added category and result-limit filtering for structurally valid VERIFIED records | Test covers valid receipt retrieval plus malformed/forged record exclusion | Verify the latest Python matrix |
| LR-03 | Receipt consistency | Retrieval checks candidate hash, manifest hash, image digest, policy, case counts, success/exit status, and timezone-aware timestamps | Code validation and tests are in the feature branch | Review tampering limits; local JSONL is not cryptographically tamper-proof |
| LR-04 | Privacy | Retrieval returns compact records only; no source code or test inputs are stored by the API | Covered by ledger record tests | Keep summaries bounded/redacted |
| LR-05 | Learning effectiveness | No semantic retrieval or future-task improvement is claimed | Not measured | Build a no-retrieval baseline before adding semantic search |

**Current phase result: IMPLEMENTED, CI PENDING.** This is schema-checked recency/category retrieval, not semantic search. It cannot prove that a local JSONL file has never been manually modified. Real Docker integration and measured benefit to future corrections remain pending.

## 16. Structured untrusted-input prompt boundary — 2026-10-22

| ID | Task-table item | Change now made | Evidence status | Next gate |
|---|---|---|---|---|
| PI-01 | Prompt input structure | Task, current source, raw failure, and analyzer excerpts are serialized as one JSON object | Unit test added with fake system/developer instructions and embedded delimiter text | Run CI across the Python matrix |
| PI-02 | Trust instructions | Prompt explicitly labels the JSON as untrusted data and rejects embedded instructions | Source change and focused regression test in feature branch | Review wording for accidental authority leakage |
| PI-03 | Output authority | Existing proposal-only rule remains; prompt text cannot authorize execution or file changes | Normal workflow remains separate from explicit Docker verifier | Preserve this separation in future agent/tool integrations |
| PI-04 | Security claims | Documentation says this is defense-in-depth, not a guarantee against prompt injection | README and correction-safety guidance updated | Add adversarial cases without claiming complete resistance |

**Current phase result: IMPLEMENTED, CI PENDING.** JSON encoding prevents embedded newlines from breaking the payload structure, but a model may still be influenced by malicious data. The security boundary remains the host code and explicit permissions, not prompt wording.

## Final recommendation

The highest-value milestone is the **correction → independent verification → evidence-backed learning workflow**. It connects existing modules and distinguishes a plausible proposal from a tested, reusable correction.

Priorities:
1. Correctness before autonomy.
2. Measured results before claims of improvement.
3. Verified learning before automatic learning.
4. Resource measurements before heavier models or longer inference.
5. Safe integration before merging stacked draft PRs.

Do not describe the project as having improved model intelligence, coding accuracy, or RAM efficiency until repeatable measurements support those claims.
