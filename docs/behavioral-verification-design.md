# Behavioral Verification Design — Fail-Closed, Docker-Isolated Python Checks

**Status:** Design proposal only; not implemented.  
**Date:** 2026-10-22  
**Related work:** Draft PR #9 adds proposal → syntax check → conservative ledger recording.  
**Constraint:** No model inference, candidate execution, image pull, or Docker invocation is performed by this document.

## 1. Purpose

Add a narrow behavioral-verification stage so Jarvis can test selected Python candidates against independently specified expected results without executing model-generated code directly on the host.

The first supported scope should be **single-callable, JSON-compatible tests**. This is intentionally narrower than arbitrary project test suites. It creates a verifiable vertical slice before supporting multi-file projects, third-party dependencies, or arbitrary test commands.

A candidate passing these tests means only that it passed the supplied cases in the declared sandbox configuration. It does not prove general correctness, absence of vulnerabilities, or correctness outside the tested inputs.

## 2. Non-negotiable safety rules

1. Never execute model-generated code directly on the host.
2. Never fall back to host execution if Docker is missing, the daemon is unavailable, or the configured image is absent.
3. Never pull or download a container image automatically. Use Docker's pull-never behavior and fail closed if the approved image is not already present.
4. Require explicit opt-in for behavioral execution. The default correction workflow remains proposal-only and syntax-only.
5. Do not mount the repository, home directory, credentials, Docker socket, SSH keys, or arbitrary host paths into the sandbox.
6. Do not pass the host environment through to the container. Construct a minimal environment and pass only required test inputs.
7. Do not let the candidate supply or modify expected results, test counts, success status, or the evidence record.
8. Do not execute arbitrary user/model-authored test code as the trusted verifier. Begin with a declarative JSON test manifest.
9. Timeouts, malformed protocol output, missing cases, worker crashes, Docker errors, and cleanup failures must fail closed.
10. A passing syntax check alone must never create a VERIFIED record.

## 3. Threat model

Treat candidate source as potentially malicious, not merely buggy. It may attempt to:

- read files or environment variables;
- access the network;
- spawn processes or consume CPU/memory indefinitely;
- terminate the process before reporting a result;
- emit misleading stdout/stderr or fake a success marker;
- tamper with the test harness or expected outputs;
- exploit writable mounts or gain access to host resources.

Docker isolation reduces exposure but is not a proof of perfect containment. The design must document Docker/daemon trust, host-kernel risk, platform limitations, and the exact image identity used.

## 4. Proposed architecture

### 4.1 Host-side controller

A trusted controller should:

1. Validate candidate source size, UTF-8 encoding, filename, entry-point name, test count, JSON input/output values, and total request size.
2. Run the existing non-executing syntax verifier first.
3. Require explicit configuration such as allow_execution=True; default must be false.
4. Check that Docker is available and the approved image digest is already present. Never pull it.
5. Create a unique temporary workspace containing only the candidate and a small fixed worker harness. Do not copy the repository or user files.
6. Mount that workspace read-only into a restricted container.
7. Send one input case at a time to the worker. Keep expected outputs only in the host controller; do not expose them to the candidate.
8. Compare worker outputs with host-held expected values. Malformed output or extra stdout must be a failure.
9. Enforce a per-case and total deadline. On timeout, explicitly stop and remove the named ephemeral container; do not leave a worker running.
10. Build the evidence receipt from controller-observed exit state, cases actually submitted and answered, expected/actual comparison outcomes, source hash, image digest, and timestamps.
11. Return a typed failure for every incomplete or ambiguous run. Do not retry a failing candidate automatically.

### 4.2 Candidate worker

The worker runs only inside the container. It loads the candidate once and invokes a named callable for each JSON input case. The candidate and worker share a container but not the host controller process.

The worker protocol should be line-delimited JSON with one response per request. The host sends inputs only, never expected outputs. The worker output is untrusted data; the host must validate its schema and compare values independently. Unexpected stdout, invalid JSON, missing responses, or extra responses cause failure.

This protocol is intended for functions whose inputs and return values are JSON-compatible. It is not a general sandbox for arbitrary shell commands or full-project test suites.

### 4.3 Container policy

The runner should use the strongest practical restrictions supported by the approved Docker environment:

- exact, digest-pinned image already present locally; pull-never behavior;
- network disabled;
- read-only root filesystem;
- non-root numeric user;
- drop Linux capabilities and enable no-new-privileges;
- strict memory, CPU, PID, and temporary-storage limits;
- a small temporary filesystem only if required;
- read-only mount of the isolated workspace;
- no host home/repository/credential/Docker-socket mounts;
- minimal environment and a fixed working directory;
- explicit container name so timeout cleanup can target only that run;
- bounded stdout/stderr capture and bounded input/output sizes.

Resource limits must be configurable only within conservative hard limits. Missing or unsupported required controls must produce an unavailable/fail-closed result, not silently weaken isolation.

**Platform note:** Docker Desktop on Windows uses a Linux VM for Linux containers. The implementation must not assume Linux host semantics or claim equivalent isolation on every Docker/runtime configuration. Verify the actual daemon and container mode before enabling the runner.

## 5. Evidence and ledger contract

A behavioral verification receipt should be created by the verifier, not accepted as an arbitrary dictionary from the caller. At minimum it should bind:

- candidate SHA-256;
- digest of the declarative test manifest;
- approved container image digest;
- sandbox policy/version;
- number of cases submitted, answered, passed, and failed;
- verifier-observed process/exit result;
- bounded elapsed time and timeout policy;
- timezone-aware timestamp;
- a concise result classification.

Only a receipt from a completed, successful run with at least one case and every required case passing may be eligible for a VERIFIED ledger record. The ledger should check that the receipt type, candidate hash, success state, counts, and image/policy identity are consistent. Do not persist raw source, raw test inputs, secrets, or full unbounded process output.

A Python type is not a security boundary against malicious code already running inside the trusted host process. The trust boundary is the reviewed controller/verifier implementation; generated code runs only inside the restricted container and cannot write the host ledger.

## 6. Resource and operational constraints

The target laptop has 8 GB RAM. The runner must:

- remain disabled by default;
- check available RAM before starting a container;
- use conservative hard limits and one verification run at a time;
- cap test count, source bytes, per-case input/output, and total wall-clock time;
- avoid model inference and model downloads during verification;
- never pull the sandbox image automatically;
- return an explicit unavailable status if Docker/image/resource prerequisites are not satisfied.

A container memory cap does not represent total host overhead. Measure host RAM and runtime latency during a deliberate, opt-in integration test before claiming the runner is resource-safe.

## 7. Required test plan

### Unit tests (no Docker invocation)

- reject execution when opt-in is false;
- reject invalid/oversized source, invalid entry point, malformed manifest, too many cases, and non-JSON values;
- verify the command includes network isolation, read-only filesystem, non-root user, resource limits, pull-never, and no host-home/repository mounts;
- fail closed on missing Docker, missing image, image-inspection errors, invalid image digest, and unsupported platform controls;
- fail closed on timeout, nonzero exit, empty/extra/malformed worker responses, mismatched output, zero cases, and worker crash;
- prove expected values stay in the host controller and are not sent to the candidate worker;
- prove no candidate source or raw output is written to the ledger;
- prove only verifier-created receipts can be considered for VERIFIED;
- prove a syntax-valid result alone cannot become VERIFIED.

### Opt-in integration tests

Only run when an operator explicitly enables sandbox integration tests and confirms the exact image is already available locally. Do not pull images. Use harmless fixtures to check successful output comparison, wrong output rejection, timeout cleanup, and network unavailability. Integration tests must report a clear skip/unavailable result when Docker or the approved image is absent.

## 8. Implementation sequence

| Phase | Work | Exit criteria |
|---|---|---|
| BV-01 | Review and approve this safety design | Threat model, supported scope, image policy, and opt-in behavior accepted |
| BV-02 | Implement manifest validation and typed result/receipt objects | Invalid input fails closed; no process execution in unit tests |
| BV-03 | Implement Docker availability/image preflight | No image pulls; absent image returns unavailable |
| BV-04 | Implement restricted container command and bounded worker protocol | Unit tests prove required flags and protocol failure behavior |
| BV-05 | Add host-side expected-output comparison | Candidate cannot provide expected values or mark its own run successful |
| BV-06 | Integrate receipt with ledger | VERIFIED accepted only from successful verifier evidence; direct status assignment remains rejected |
| BV-07 | Add opt-in Docker integration tests | Success/failure/timeout cleanup demonstrated using preloaded image |
| BV-08 | Integrate into correction workflow behind explicit opt-in | Default behavior remains proposal-only; no silent execution |
| BV-09 | Measure RAM/CPU/latency on target laptop | Fresh preflight and recorded measurements; no unsupported resource claims |

## 9. Acceptance criteria

Do not call behavioral verification complete until all of these are true:

- candidate code is never executed directly on the host;
- no image downloads or host fallback occur;
- expected values remain outside the candidate execution environment;
- every case and output is validated by the host controller;
- timeout and cleanup paths are tested;
- missing prerequisites fail closed;
- only verifier-generated, candidate-bound receipts can support VERIFIED;
- the entire unit suite passes across supported Python versions;
- opt-in sandbox integration tests pass using a preloaded, pinned image;
- the correction workflow remains non-executing unless the operator explicitly enables the verifier.

Until then, keep the existing syntax-only workflow and VERIFIED lock in place.
