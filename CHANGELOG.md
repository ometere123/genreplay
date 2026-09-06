# Changelog

## 0.2.0 - 2026-09-06

Submission-hardening release.

### Live evidence and reviewer workflow

- Added `genreplay evidence` to generate a reviewer-ready evidence directory from a real GenLayer transaction.
- Added transaction-aware `doctor --tx-id` that performs actual capture and validator replay probing.
- Added a strict Bradbury `live-evidence` GitHub workflow with uploaded failure/success artifacts.
- Added `docs/SUBMISSION_EVIDENCE.md` with reproducible public transaction cases and evidence rules.
- Evidence bundles now commit every generated reviewer artifact by SHA-256 and byte length and expose offline bundle verification through the Python API.

### Replay semantics

- Added consensus `timeline` reports and deterministic protocol-evidence `explain` reports.
- Added `replay --all-rounds` for trace-backed round replay.
- Added explicit `replay --receipt-current` for transaction-level stored-proposal replay.
- Added `fork --receipt-current` for counterfactual stored-proposal scenarios.
- Added dependency-free canonical RLP decoding of receipt `eqBlocksOutputs`.
- Strip only the final exact protocol `padded` sentinel and reject padding-only replay evidence.
- Never attribute transaction-level receipt outputs to a historical round in multi-round history.
- Replay scenarios now use `round_number = null` for transaction-level evidence.
- Every replay records its leader-results provenance.
- Distinguish `NOT_VOTED` from explicit runtime failure so historical receipts are not over-interpreted.

### Protocol compatibility

- Normalize numeric v0.6/testnet transaction status codes while preserving raw receipt values.
- Normalize numeric execution-result codes independently from consensus status.
- Added human-readable round-result names.
- Hardened handling of Bradbury RPC differences discovered through real-network evidence.

### Infrastructure API

- Added stable high-level `GenReplay` Python API.
- Added machine-readable schema-versioned JSON output for submission-critical reports.
- Added `GenReplay.verify_evidence(...)` for offline reviewer-bundle validation.
- Bumped package version to `0.2.0` through a dedicated version module.

### Capsule security

- Reject duplicate ZIP member names.
- Reject absolute, traversal, backslash, dot-component, and reserved payload paths.
- Reject undeclared and missing payloads.
- Enforce manifest, individual-entry, file-count, and total-uncompressed-size limits before payload loading.
- Verify manifest-declared sizes against ZIP metadata before reading payloads.

### Verification

- Expanded tests for numeric protocol enums, RLP decoding, provenance, stored-proposal replay, deep doctor, evidence generation, evidence tamper detection, `NOT_VOTED` semantics, and malicious capsules.
- Standard CI now verifies Python 3.11/3.12/3.13, Ruff, pytest, compileall, CLI smoke paths, public API imports, and wheel construction.

## 0.1.0 - 2026-09-06

Initial alpha release.

- Versioned `.genreplay` ZIP capsule with SHA-256 payload manifest.
- Capture of transaction receipt, lifecycle, round traces, historical contract source/schema/state.
- Consensus-aware analysis that separates status from execution success.
- Validator-mode replay through `gen_call.leader_results`.
- Counterfactual scenario export and execution.
- Conservative leader-results prefix minimization.
- Structural capsule diffing.
- Pytest regression export.
- Built-in current GenLayer network presets.
- Dependency-free runtime JSON-RPC client.
