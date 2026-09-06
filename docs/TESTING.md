# Testing Strategy

GenReplay is infrastructure that interprets protocol evidence. Tests therefore focus on preventing silent evidence corruption, unsafe archive handling, and semantic overclaiming.

## Offline suite

Run:

```bash
pytest -q
```

The offline suite requires no Docker, wallet, LLM provider, or GenLayer network.

Coverage includes:

- current built-in network identities;
- raw JSON-RPC envelope handling and error propagation;
- exact GenLayer parameter names (`txId` versus debug `txID`);
- v0.6/testnet numeric transaction and execution-result normalization;
- capture of multiple consensus rounds;
- partial/pruned debug trace handling;
- historical state block selection;
- contract source/schema/state capture;
- SHA-256 capsule integrity and tamper rejection;
- deterministic capsule serialization;
- duplicate ZIP-member rejection;
- traversal/unsafe-path rejection;
- undeclared payload rejection;
- capsule size/file-count limits;
- consensus status versus execution-success rules;
- nondeterministic disagreement diagnostics;
- protocol RLP decoding of receipt `eqBlocksOutputs`;
- padding-sentinel removal;
- round-attributed validator `leader_results` construction;
- transaction-level stored-proposal replay without false round attribution;
- refusal to call empty/padding-only evidence a validator replay;
- deep transaction-aware doctor capability probing;
- reviewer evidence bundle generation;
- deterministic timeline/explanation reports;
- conservative prefix minimization;
- structural capsule diffs;
- portable pytest regression export;
- CLI machine-readable output paths;
- public Python API behavior.

## Standard CI

`.github/workflows/ci.yml` runs on Python 3.11, 3.12, and 3.13.

Every matrix job must pass:

```text
pip install -e '.[dev]'
ruff check .
pytest -q
python -m compileall -q genreplay tests
python -m genreplay --version
python -m genreplay networks
public API import assertions
python -m pip wheel . --no-deps -w dist
```

The wheel check matters because GenReplay is distributed as tooling rather than as a deployed app.

## Real-network evidence CI

Real public RPC checks run separately in:

```text
.github/workflows/live-evidence.yml
```

They are separate because public development networks may reset, rate-limit, change historical retention, or expose different debug capabilities from local Studio/Localnet environments. Those conditions should not make deterministic unit tests flaky, but they **must** be visible before a submission/release.

The live workflow currently exercises two Bradbury cases.

### Compatibility / negative replay control

```text
0x563f046c187d711127c51213ca62e2e4fee52009a98f0989a73a0a0382d21890
```

This is a transaction used by GenLayer's JavaScript SDK smoke tests. It proves real capture and numeric v0.6 result handling. Its public replay evidence is padding-only, so GenReplay must refuse validator replay rather than manufacture one.

### Nondeterministic multi-round replay case

```text
0x6bef2019bdb2fbb40204f459530b1c1ddd4c6358147ad89bb12750d2a1273b93
```

This public Bradbury transaction exposes multi-round consensus history, historical source/state, debug traces, and substantive transaction-level `eqBlocksOutputs`.

Its per-round traces do not expose historical `eq_outputs`, so GenReplay must preserve the distinction:

```text
round trace output -> round-attributed replay
receipt eqBlocksOutputs -> transaction-level replay, round_number = null
```

The workflow requires at least one real validator-mode replay to succeed for this evidence case before the release gate is considered green.

## Evidence artifact retention

The live workflow uses `actions/upload-artifact` with `if: always()` so failures still produce inspectable evidence. This is deliberate: a network/RPC incompatibility is useful release evidence and must not disappear merely because a gate failed.

Each evidence bundle contains the capsule, integrity result, analysis, timeline, deterministic explanation, capture gaps, and replay attempts.

See [`SUBMISSION_EVIDENCE.md`](SUBMISSION_EVIDENCE.md).

## Failure injection

The fake RPC suite deliberately supports partial failures. New capture/replay surfaces should include cases where:

- method is unsupported;
- history is pruned;
- response type is malformed;
- JSON-RPC error includes code/data;
- one round succeeds and another fails;
- trace output is empty while receipt output exists;
- receipt output contains only protocol padding;
- transaction-level output exists across multi-round history;
- archive content is malicious or malformed.

A best-effort capture remains inspectable whenever the required receipt was captured, but replay must fail closed when substantive leader evidence is unavailable.
