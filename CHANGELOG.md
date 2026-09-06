# Changelog

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
