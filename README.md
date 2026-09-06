# GenReplay

**Replay GenLayer consensus, not just transactions.**

GenReplay is pure developer infrastructure for capturing a GenLayer Intelligent Contract transaction as a portable, integrity-checked replay capsule and then rerunning its **leader equivalence outputs through GenVM validator mode**.

It has no frontend, no wallet flow, and no Intelligent Contract of its own. It works on *your* contracts and *your* GenLayer transactions.

```text
live GenLayer transaction
        │
        ├─ receipt / rounds / committee / vote hashes
        ├─ advanced lifecycle projection
        ├─ per-round GenVM debug traces + eq_outputs
        ├─ historical contract code / schema / state (when available)
        ▼
   .genreplay capsule
        │
        ├─ inspect / integrity verify / diff
        ├─ validator-mode protocol replay
        ├─ counterfactual target/sender/block/RPC forks
        ├─ conservative leader-output prefix minimization
        └─ pytest regression export
```

## Why this exists

A GenLayer execution is not adequately described by an EVM receipt. The protocol has a leader, a validator committee, equivalence outputs, commit/reveal rounds, possible rotations and appeals, and a distinction between consensus status and execution success.

When a real transaction behaves unexpectedly, developers need to answer questions such as:

- Which round and committee produced the decision?
- What leader equivalence outputs were validators judging?
- Does the captured proposal still pass the validator path today?
- Does a patched or separately deployed contract reject the historical proposal?
- Does the behavior change on another GenLayer environment?
- Can a live failure become a permanent regression test?

GenReplay makes those questions executable.

## What GenReplay is not

GenReplay deliberately avoids claims the network cannot support:

- It does **not** claim to reconstruct private raw HTTP/LLM responses that were never exposed by the node.
- It does **not** claim that a replay against today's validator configuration is identical to every historical validator's private execution environment.
- It does **not** mutate opaque GenVM equivalence bytes and call the result a valid counterexample.
- It does **not** infer success from `ACCEPTED` or `FINALIZED` alone.

Historical captures are **protocol replay**: protocol-visible receipt, lifecycle, traces, equivalence outputs, code, schema and state. A future instrumented capture mode can add full raw nondeterminism snapshots when those inputs are intentionally recorded during development.

## Installation

```bash
python -m pip install -e .
# or once published
pip install genreplay
```

Python 3.11+ is supported. GenLayer's own current testing stack commonly targets Python 3.12+.

## Quick start

### 1. Check an RPC

```bash
genreplay doctor --network studionet
```

Built-in presets:

```bash
genreplay networks
```

### 2. Capture a transaction

```bash
genreplay capture \
  0xYOUR_32_BYTE_GENLAYER_TRANSACTION_ID \
  --network studionet \
  -o incident.genreplay
```

Or point at any compatible GenLayer node:

```bash
genreplay capture 0x... --rpc http://localhost:4000/api -o incident.genreplay
```

### 3. Inspect the consensus event

```bash
genreplay inspect incident.genreplay
```

Example shape:

```text
GenReplay capsule v1
transaction : 0x...
captured    : 2026-09-06T00:00:00Z
network     : studionet
chain id    : 61999
status      : Finalized
execution   : FinishedWithReturn
successful  : True
rounds      : 1
trace rounds: 0
files       : 11
warnings    : 0
```

### 4. Verify capsule integrity

```bash
genreplay verify incident.genreplay
```

Every payload file is SHA-256 committed by `manifest.json`.

### 5. Replay the captured leader result through validator mode

```bash
genreplay replay incident.genreplay --network studionet
```

GenReplay obtains the selected round's `eq_outputs` from the captured trace and calls `gen_call` with `leader_results`, which instructs GenVM to execute the validator path.

A replay reports a compact diagnostic signature including:

```json
{
  "status_code": 0,
  "status_message": "success",
  "nondet_disagreement_call": null,
  "return_data": "0x...",
  "stderr_present": false,
  "event_count": 0,
  "message_count": 0
}
```

### 6. Fork the experiment

Export a mutable scenario:

```bash
genreplay fork incident.genreplay -o candidate.json
```

Counterfactual examples:

```bash
# Replay against another deployed contract implementation
genreplay fork incident.genreplay \
  --target 0xPATCHED_CONTRACT \
  --latest-state \
  -o patched.json

genreplay run-scenario patched.json --network studionet

# Replay on localnet
genreplay run-scenario candidate.json --network localnet

# Pin different historical state
genreplay fork incident.genreplay --block 0x151ec5 -o historical.json
```

The scenario format is intentionally plain JSON so CI systems and coding agents can manipulate it without importing GenReplay.

### 7. Conservatively minimize a validator counterexample

```bash
genreplay minimize candidate.json \
  --rpc http://localhost:4000/api \
  -o minimized.json
```

Equivalence outputs are opaque. GenReplay therefore performs only an ordered-prefix reduction. Each shorter prefix is executed against real `gen_call`; it is kept only if the diagnostic signature is exactly preserved. Trial evidence is written beside the minimized scenario.

### 8. Turn a production incident into a regression test

```bash
genreplay export-test incident.genreplay \
  -o tests/test_consensus_incident.py
```

The generated test copies the capsule into `tests/replays/` beside the test tree so the regression is portable and committable. It always verifies capsule integrity offline. Set `GENREPLAY_RPC` in CI to enable the live validator replay assertion.

## Commands

| Command | Purpose |
|---|---|
| `networks` | Show GenLayer RPC presets and chain IDs |
| `doctor` | Zero-side-effect RPC connectivity check |
| `capture` | Build a `.genreplay` archive from a live transaction |
| `inspect` | Summarize status, execution, rounds, warnings and capture gaps |
| `verify` | Verify file sizes and SHA-256 commitments |
| `replay` | Validator-mode replay using captured leader equivalence outputs |
| `fork` | Export a mutable counterfactual scenario |
| `run-scenario` | Execute a saved scenario |
| `minimize` | Reduce leader-result prefix while preserving replay signature |
| `diff` | Structurally compare two capsules |
| `export-test` | Generate capsule-backed pytest regression tests |

Use `genreplay <command> --help` for all options.

## Capsule contents

A typical capsule contains:

```text
manifest.json
transaction/receipt.json
transaction/lifecycle.json
traces/round-000.json
traces/round-001.json
contract/source.b64
contract/source.py
contract/source.sha256
contract/schema.json
contract/state.hex
analysis/summary.json
capture/issues.json
```

The archive format is specified in [`docs/CAPSULE_SPEC.md`](docs/CAPSULE_SPEC.md).

## GenLayer surfaces used

GenReplay intentionally integrates at the node/RPC level rather than hiding consensus details behind a generic blockchain abstraction:

- `eth_chainId`
- `gen_getTransactionReceipt`
- `gen_getTransactionLifecycle`
- `gen_dbg_traceTransaction`
- `gen_getContractCode`
- `gen_getContractState`
- `gen_getContractSchema`
- `gen_call` with `leader_results` validator mode

See [`docs/RPC_COMPATIBILITY.md`](docs/RPC_COMPATIBILITY.md) and [`docs/REFERENCES.md`](docs/REFERENCES.md).

## Consensus-aware outcome model

GenReplay treats a transaction as successful only when both are true:

1. consensus status is `Accepted` or `Finalized`; and
2. execution result is `FinishedWithReturn`.

A finalized user error remains an error. An `Undetermined` transaction is not treated as successful just because a leader produced data.

## Architecture

The implementation is intentionally dependency-light:

```text
genreplay.rpc       raw JSON-RPC transport
genreplay.capture   protocol evidence collector
genreplay.capsule   deterministic ZIP + integrity manifest
genreplay.analysis  consensus/lifecycle diagnostics
genreplay.replay    scenario construction + validator replay
genreplay.diffing   structural capsule comparison
genreplay.export    pytest regression generation
genreplay.cli       operator/developer interface
```

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for trust boundaries and failure handling.

## Security and privacy

Replay capsules may contain contract source, state snapshots, logs, return data and protocol metadata. Treat them as engineering evidence, not automatically public artifacts. GenReplay does not collect private keys and does not need a browser wallet.

See [`SECURITY.md`](SECURITY.md).

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check .
python -m genreplay networks
```

The offline verification strategy is documented in [`docs/TESTING.md`](docs/TESTING.md). No Docker is required for the offline test suite. Live replay requires a compatible GenLayer RPC. Local full-network experiments can target a developer's existing Localnet/Studio setup.

## Project boundary

GenReplay is intentionally **not a reusable Intelligent Contract**. It defines no contract and does not ask developers to deploy a GenReplay contract. The object under test is the developer's existing GenLayer execution.

## Status

`0.1.0` is an alpha protocol-replay release. The capsule format is versioned from day one so future instrumentation, committee replay adapters and richer nondeterminism capture can evolve without silently changing old evidence.

## License

MIT
