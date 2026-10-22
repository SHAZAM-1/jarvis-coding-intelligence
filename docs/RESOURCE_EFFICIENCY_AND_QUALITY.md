# Resource Efficiency Without Quality Degradation

## Mandatory engineering principle

**Maximize useful intelligence per unit of resource consumed. Minimize waste, not capability.**

This policy applies to Jarvis Coding Intelligence implementation, runtime behavior, model routing, testing, benchmarks, and performance changes. It does not reorder the 16 tasks in `docs/MASTER_TASK_TRACKER.md`.

Priority order:

1. Correctness and reliability.
2. Security and data integrity.
3. Reasoning quality and successful task completion.
4. Efficient RAM, CPU, storage, latency, and inference time.
5. Convenience and optional features.

Never trade away mandatory correctness, security, regression checks, or verification silently to reduce resource use. When a task cannot complete within the available budget, report it as blocked/incomplete rather than successful.

## Measure before optimizing

Before a material performance change, establish a reproducible baseline on the actual target machine. Record:

- Hardware/OS, Python and Ollama versions, installed model identifiers, runtime configuration, and background workload.
- Available and used RAM at start, peak process/system RAM during representative work, and how peak values were captured.
- CPU utilization during idle, inference, coding, tests, and tool execution.
- Model load time, request latency, throughput, context/token budgets, and repeated inference where measurable.
- Task-level success, exact expected-result checks, regressions, test outcomes, timeouts, and failure modes.
- Worker/subprocess counts, duplicate model instances, and resource use under concurrency.
- Workload, warm/cold model state, number of repetitions, measurement tools, and uncertainty/limitations.

Use identical tasks and conditions for before/after comparisons where possible. Separate deterministic unit-test evidence from real-model, real-container, and end-to-end evidence. Do not invent measurements or treat a smoke test as a broad quality benchmark.

## Optimize waste before capability

Prioritize these changes when evidence supports them:

- Avoid duplicate model loads and simultaneous large models unless measured benefit justifies the cost. Reuse a loaded model when appropriate; measure unload/reload trade-offs.
- Retrieve only relevant files, symbols, and documentation. Prefer incremental analysis of changed files and dependencies; do not repeatedly scan unchanged content without a reason.
- Cache only when cache keys, freshness, invalidation, and correctness are demonstrable. Never allow stale cache results to hide defects.
- Bound retries and tool calls; define stopping conditions and retain structured intermediate evidence.
- Use deterministic tools for deterministic operations rather than unnecessary inference.
- Run independent tasks concurrently only when it improves total efficiency. Bound workers and serialize memory-heavy operations under pressure. Prevent duplicate agents from repeating the same investigation.
- Run focused tests first, then all mandatory regression, security, and acceptance tests. Never skip required checks merely to save CPU.
- Cancel obsolete work safely and release resources without deleting user data, diagnostics, or active work.

## Preserve reasoning and route by evidence

Shorter output, fewer tokens, lower latency, and smaller models are not by themselves proof of success. Complex coding, multi-file debugging, architecture, and security tasks need enough context to understand dependencies and failure causes.

Model routing must use installed/configured models only and be backed by repeatable task outcomes. A lightweight tier may handle low-risk routine work; more complex or uncertain work may use a stronger already-available model, sequential execution, deterministic analysis, targeted tests, or independent review. Do not assume a larger model can run alongside the current model within the laptop's memory budget. Keep selection configurable and preserve a reliable fallback. Do not download models or weights without separate approval.

## Resource budgets and backpressure

The target laptop has approximately 8 GB RAM, but actual hardware and available memory must be re-detected before setting operational limits. Account for Windows, WSL2, Docker, Ollama, model weights/KV cache, development tools, and test runners; never allocate all RAM to Jarvis.

Derive budgets from measurements, not universal assumptions. Under pressure, stop optional background work, reduce optional concurrency, cancel redundant/obsolete jobs safely, and prefer sequential or incremental work. Preserve mandatory quality and security checks. Record any operation that cannot complete within the budget.

Current runtime guards and thresholds are protective defaults, not proof that the machine has enough memory for a specific operation. In particular, the latest reported laptop snapshot showed only 853 MiB available RAM; do not run model inference or a real Docker smoke test on that stale snapshot. Recheck live memory and prerequisites immediately before such operations.

## Performance regression gates

For each material optimization, record the baseline and new:

- Peak RAM and available RAM.
- CPU utilization, latency, and throughput.
- Task success rate, expected-result checks, regression count, and required test outcomes.
- Quality benchmark results on the same fixed workload.
- New limitations, uncertainty, and failure modes.

Accept a change only when quality and reliability remain within documented tolerances and the resource benefit is reproducible. If memory falls but coding accuracy, debugging success, security, or verification quality regresses beyond tolerance, reject or redesign the change. If quality cannot yet be measured adequately, mark the optimization **provisional** rather than claiming success.

## Required acceptance criteria

This objective is complete only when evidence demonstrates all of the following:

1. A documented, reproducible baseline with method, workload, environment, and limitations.
2. Measured resource improvement, or a documented evidence-backed conclusion that an optimization was not beneficial.
3. No material regression against an agreed repeatable quality benchmark.
4. Passing required tests and relevant regression/security checks.
5. Stable behavior across repeated tasks and realistic resource pressure.
6. Safe recovery from timeout, cancellation, and insufficient memory.
7. Updated documentation and evidence-backed updates to the relevant rows in the ordered master task table.

CI passing alone is insufficient. If measurement or quality evidence is missing, explicitly report the gap and keep the optimization provisional.