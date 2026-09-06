# GenReplay

**Replay GenLayer consensus, not just transactions.**

GenReplay is pure developer infrastructure for turning a GenLayer Intelligent Contract transaction into a portable, integrity-checked consensus artifact and then replaying protocol-visible leader evidence through **GenVM validator mode**.

It has **no frontend, no browser wallet flow, and no Intelligent Contract of its own**. Developers bring their own contracts and transactions.

```text
real GenLayer transaction
        │
        ├─ receipt / committee / round history / votes
        ├─ lifecycle projection when exposed
        ├─ GenVM debug traces
        ├─ transaction-level eqBlocksOutputs
        ├─ historical contract code / schema / state when exposed
        ▼
   .genreplay capsule
        │
        ├─ verify / inspect / timeline / explain
        ├─ round-attributed validator replay
        ├─ transaction-level stored-proposal replay
        ├─ counterfactual fork / minimize / diff
        ├─ pytest regression export
        └─ reviewer-ready evidence bundle
```

## Why this exists

A GenLayer transaction is not adequately described by an ordinary deterministic-chain receipt. A single execution may involve a leader, a validator committee, nondeterministic equivalence outputs, commit/reveal rounds, rotations, appeals, timeouts, and separate **consensus status** and **execution result** semantics.

When something behaves unexpectedly, developers need to answer questions such as:

- Which committees and leaders participated across the consensus history?
- Did the transaction finalize even though contract execution failed?
- Which protocol-visible equivalence outputs are available for validator replay?
- Are those outputs attributable to a particular round or only to the stored transaction proposal?
- Does the captured proposal still pass the validator path today?
- Does a patched or separately deployed contract reject the same proposal?
- Can this incident become a permanent CI regression?

GenReplay makes those questions executable and preserves the evidence used to answer them.

## What GenReplay does not claim

GenReplay deliberately rejects evidence overclaiming:

- A public historical transaction does **not** reveal private HTTP/LLM responses that the node never exposed.
- `gen_call` validator mode is a validator-path execution, **not** a newly assembled stake-weighted consensus committee.
- Transaction-level `eqBlocksOutputs` are **not assigned to a historical round** unless the evidence makes that attribution unambiguous.
- Opaque GenVM equivalence outputs are never arbitrarily edited and called a valid counterexample.
- `ACCEPTED` or `FINALIZED` alone never means the contract execution succeeded.
- A capsule hash proves post-capture integrity; it does not prove that a malicious source RPC told the truth.

These boundaries are part of the implementation, not only documentation.

## Installation

```bash
python -m pip install -e .
```

The runtime has no mandatory third-party dependencies. Python 3.11, 3.12, and 3.13 are verified in CI.

## Submission-grade quick path

The fastest way to prove GenReplay against a real transaction is now:

```bash
genreplay doctor \
  --network testnet-bradbury \
  --tx-id 0xYOUR_TRANSACTION \
  --json

genreplay evidence \
  0xYOUR_TRANSACTION \
  --network testnet-bradbury \
  -o evidence/transaction \
  --json
```

`doctor --tx-id` performs an actual in-memory capture and attempts validator replay. It grades the environment as one of:

```text
FULL
REPLAY_READY_PARTIAL_CAPTURE
CAPTURE_ONLY
CONNECTIVITY_ONLY
UNAVAILABLE
```

`evidence` creates a reviewer-friendly directory containing:

```text
evidence.json
incident.genreplay
integrity.json
analysis.json
timeline.json
explanation.json
capture-issues.json
replays/
  round-000.json
  round-001.json
  ...
  receipt-current.json
```

Every unsuccessful replay attempt remains in the evidence bundle. Missing protocol evidence is not silently discarded.

## Capture

```bash
genreplay capture \
  0xYOUR_32_BYTE_TRANSACTION_ID \
  --network studionet \
  -o incident.genreplay
```

Or target a compatible node directly:

```bash
genreplay capture 0x... --rpc http://localhost:4000/api -o incident.genreplay
```

A capture can preserve:

- raw transaction receipt;
- round and committee history;
- lifecycle projection when supported;
- per-round debug traces;
- transaction-level `eqBlocksOutputs`;
- contract source;
- source SHA-256;
- schema;
- historical contract state;
- analysis warnings;
- explicit capture gaps.

Only the transaction receipt is mandatory. Optional surface failures are recorded in `capture/issues.json` so a partial forensic artifact remains inspectable.

## Inspect, timeline, and explain

```bash
genreplay inspect incident.genreplay

genreplay timeline incident.genreplay

genreplay explain incident.genreplay
```

Machine-readable form:

```bash
genreplay inspect incident.genreplay --json
genreplay timeline incident.genreplay --json
genreplay explain incident.genreplay --json
```

All new v0.2 reports include a schema version.

`timeline` exposes consensus history and round-to-round changes. `explain` is deliberately deterministic and rule-based; it does **not** send protocol evidence to a centralized AI model.

Example explanation causes include:

```text
NONDETERMINISTIC_DISAGREEMENT
CONSENSUS_UNDETERMINED
CONSENSUS_TIMEOUT
EXECUTION_FAILED_AFTER_CONSENSUS
CONSENSUS_AND_EXECUTION_SUCCEEDED
```

## Two replay modes

GenReplay 0.2 explicitly distinguishes two evidence classes.

### 1. Round-attributed replay

When a captured round trace exposes substantive `eq_outputs`:

```bash
genreplay replay incident.genreplay --round 0 --network studionet
```

For every trace-backed round:

```bash
genreplay replay incident.genreplay --all-rounds --network studionet
```

The resulting scenario has a concrete `round_number` and its provenance says the leader results came from that round's trace.

### 2. Transaction-level stored-proposal replay

Some public/testnet receipts expose transaction-level `eqBlocksOutputs` while debug traces do not expose per-round equivalence outputs. GenReplay decodes the protocol RLP payload and can replay it without inventing round attribution:

```bash
genreplay replay incident.genreplay \
  --receipt-current \
  --network testnet-bradbury
```

This scenario intentionally stores:

```json
{
  "round_number": null
}
```

and records that the evidence came from transaction-level `receipt.eqBlocksOutputs`.

For single-round transactions, receipt output fallback may be treated as unambiguous round evidence. For multi-round history, it remains explicitly transaction-level.

## Counterfactual replay

Fork a historical proposal into a mutable scenario:

```bash
genreplay fork incident.genreplay \
  --round 0 \
  -o scenario.json
```

Or fork the transaction-level stored proposal:

```bash
genreplay fork incident.genreplay \
  --receipt-current \
  -o stored-proposal.json
```

Replay against another deployed contract revision:

```bash
genreplay fork incident.genreplay \
  --receipt-current \
  --target 0xPATCHED_CONTRACT \
  --latest-state \
  -o patched.json

genreplay run-scenario patched.json --network studionet
```

`--latest-state` exists because a newly deployed candidate may not have existed at the original transaction block. GenReplay requires that context change to be explicit.

## Conservative counterexample minimization

```bash
genreplay minimize scenario.json \
  --rpc http://localhost:4000/api \
  -o minimized.json
```

Equivalence outputs are opaque protocol bytes. GenReplay therefore performs only ordered-prefix reduction. Every shorter candidate is executed through actual validator-mode `gen_call`; it is retained only if the diagnostic signature exactly matches the target behavior. Trial evidence is written next to the minimized scenario.

## Production incident → regression test

```bash
genreplay export-test incident.genreplay \
  -o tests/test_consensus_incident.py
```

The generated test stores the replay capsule under `tests/replays/`, verifies capsule integrity offline, and can enable live validator replay when `GENREPLAY_RPC` is set in CI.

## Python API

GenReplay is also a library:

```python
from genreplay import GenReplay

replay = GenReplay("https://rpc-bradbury.genlayer.com")

report = replay.doctor(tx_id="0x...")
capsule = replay.capture("0x...")

timeline = replay.timeline(capsule)
explanation = replay.explain(capsule)

# Round-attributed replay when per-round evidence exists.
round_result = replay.replay(capsule, round_number=0)

# Transaction-level stored proposal, deliberately not round-attributed.
stored_result = replay.replay_receipt(capsule)
```

## Commands

| Command | Purpose |
|---|---|
| `networks` | Show built-in GenLayer RPC presets and chain IDs |
| `doctor` | Probe connectivity; with `--tx-id`, prove capture/replay capabilities |
| `capture` | Create a versioned `.genreplay` artifact from a real transaction |
| `evidence` | Generate a reviewer-ready live transaction evidence bundle |
| `inspect` | Summarize consensus status, execution result, warnings, and capture gaps |
| `verify` | Verify declared sizes and SHA-256 payload commitments |
| `timeline` | Show consensus rounds and round-to-round changes |
| `explain` | Produce a deterministic protocol-evidence explanation |
| `replay` | Run round-attributed or transaction-level leader evidence through validator mode |
| `fork` | Export a mutable counterfactual scenario |
| `run-scenario` | Execute a saved validator-mode scenario |
| `minimize` | Reduce the leader-result prefix while preserving the replay signature |
| `diff` | Structurally compare two capsules |
| `export-test` | Generate a capsule-backed pytest regression |

## GenLayer surfaces used

GenReplay integrates directly with GenLayer protocol/debug RPCs:

```text
eth_chainId
gen_getTransactionReceipt
gen_getTransactionLifecycle
gen_dbg_traceTransaction
gen_getContractCode
gen_getContractState
gen_getContractSchema
gen_call + leader_results
```

The raw protocol objects are preserved rather than normalized away behind a generic blockchain abstraction.

## Consensus-aware outcome model

GenReplay treats a transaction as successful only when both conditions hold:

1. consensus status is accepted/finalized; and
2. execution result finished with return.

Numeric v0.6/testnet receipt enums are normalized to their protocol names. A finalized `FINISHED_WITH_ERROR` remains an execution failure.

## Capsule security

`.genreplay` files are untrusted forensic input. The v0.2 loader rejects:

- duplicate ZIP members;
- absolute, traversal, and unsafe paths;
- undeclared ZIP payloads;
- missing declared payloads;
- manifest/ZIP size mismatches;
- oversized manifests;
- oversized entries;
- excessive payload counts;
- excessive total uncompressed size;
- SHA-256 mismatches.

Normal inspection/replay does not extract arbitrary capsule paths to disk.

## Verification

Standard CI runs on Python 3.11, 3.12, and 3.13 and requires:

```text
editable package install
Ruff
full pytest suite
compileall
CLI version/network smoke
public Python API imports
wheel construction
```

A separate `live-evidence` workflow exercises real Bradbury transactions and uploads the evidence directory even on failure so public-network incompatibilities remain inspectable rather than hidden.

See [`docs/SUBMISSION_EVIDENCE.md`](docs/SUBMISSION_EVIDENCE.md), [`docs/TESTING.md`](docs/TESTING.md), and [`docs/REPLAY_SEMANTICS.md`](docs/REPLAY_SEMANTICS.md).

## Architecture

```text
genreplay.rpc       raw JSON-RPC transport
genreplay.capture   protocol evidence collector
genreplay.codec     receipt equivalence-output RLP decoding
genreplay.capsule   deterministic ZIP + integrity/security boundary
genreplay.analysis  consensus/execution diagnostics
genreplay.report    timeline + deterministic explanation
genreplay.replay    validator replay + counterfactual scenarios
genreplay.evidence  reviewer evidence bundle generation
genreplay.diffing   structural capsule comparison
genreplay.export    pytest regression generation
genreplay.client    public Python API
genreplay.cli       developer/operator interface
```

## Project boundary

GenReplay is intentionally **not a reusable Intelligent Contract**. It defines no GenReplay contract and asks developers to deploy none. The object being captured and replayed is the developer's existing GenLayer consensus execution.

## Status

`0.2.0` is the submission-hardening release. Capsule format remains v1; machine-readable reports use their own schema versions so reporting can evolve without silently changing archived evidence.

## License

MIT
