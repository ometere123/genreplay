# Submission Evidence

GenReplay is pure GenLayer developer infrastructure. It has no project-owned Intelligent Contract, frontend, browser wallet flow, or centralized AI decision service. The evidence below is designed to prove the tool against **real GenLayer protocol data**, not only fixture-driven tests.

## Evidence standard

A submission-grade GenReplay proof must establish all of the following independently:

1. a real GenLayer transaction can be captured;
2. the `.genreplay` capsule passes integrity verification;
3. consensus status and contract execution result are reported separately;
4. available committee/round history is preserved;
5. missing RPC evidence is recorded explicitly rather than fabricated;
6. validator-mode replay occurs only when substantive `leader_results` evidence exists;
7. replay evidence states whether it is round-attributed or transaction-level;
8. machine-readable evidence can be reproduced by CI.

The `live-evidence` GitHub workflow enforces these properties on public Bradbury data. It uploads the evidence directory even when a gate fails so incompatibilities remain inspectable.

## Real case A — official SDK compatibility / negative replay control

Transaction:

```text
0x563f046c187d711127c51213ca62e2e4fee52009a98f0989a73a0a0382d21890
```

Network:

```text
Bradbury
chain id 4221
https://rpc-bradbury.genlayer.com
```

This transaction is used by GenLayer's JavaScript SDK smoke tests. GenReplay's live capture established:

- real Bradbury receipt capture succeeds;
- numeric transaction status `7` is normalized as `FINALIZED`;
- numeric execution result `2` is normalized as `FINISHED_WITH_ERROR`;
- the transaction has a consensus round with a majority result;
- the public debug trace is available but exposes no substantive `eq_outputs`;
- receipt `eqBlocksOutputs` decodes to the protocol padding sentinel only;
- GenReplay therefore **refuses to manufacture validator replay evidence** from this transaction.

This is intentionally retained as a negative control. It proves two important GenReplay behaviors:

1. `FINALIZED` is not reported as successful execution when the execution result is an error; and
2. the presence of an `eqBlocksOutputs` field is not enough to claim replayability when it contains no substantive output.

## Real case B — multi-round nondeterministic transaction

Transaction:

```text
0x6bef2019bdb2fbb40204f459530b1c1ddd4c6358147ad89bb12750d2a1273b93
```

Network:

```text
Bradbury
chain id 4221
https://rpc-bradbury.genlayer.com
```

This is a public nondeterministic resolution transaction from a real GenLayer project. Live capture has established that it exposes substantially richer protocol evidence:

- capsule integrity passes;
- historical contract source is available;
- historical contract state is available;
- multiple debug trace rounds are available;
- receipt contains multi-round/appeal-style consensus history with changing committee sizes and outcomes;
- transaction-level `eqBlocksOutputs` contains a substantive stored result, not only padding;
- the public round traces do not expose per-round `eq_outputs` for this historical transaction.

The receipt equivalence-output payload decodes to a substantive output representing:

```json
{"outcome":"YES"}
```

plus the protocol padding sentinel.

### Why this case changed GenReplay 0.2

The public receipt exposes transaction-level equivalence output bytes but does not bind those bytes to a specific historical round. GenReplay therefore has two separate replay concepts:

**Round-attributed replay**

```text
trace round N -> eq_outputs -> round_number = N
```

**Transaction-level stored-proposal replay**

```text
receipt eqBlocksOutputs -> leader_results -> round_number = null
```

The second mode never claims that the stored receipt output came from round 0, round 1, or another specific historical round.

That distinction is enforced in code, JSON output, evidence metadata, tests, and CLI behavior.

## Reproduce the live proof

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

CAPTURE_TX=0x563f046c187d711127c51213ca62e2e4fee52009a98f0989a73a0a0382d21890
REPLAY_TX=0x6bef2019bdb2fbb40204f459530b1c1ddd4c6358147ad89bb12750d2a1273b93

genreplay doctor \
  --network testnet-bradbury \
  --tx-id "$CAPTURE_TX" \
  --json

genreplay evidence "$CAPTURE_TX" \
  --network testnet-bradbury \
  --output evidence/capture-control \
  --no-replay \
  --json

genreplay doctor \
  --network testnet-bradbury \
  --tx-id "$REPLAY_TX" \
  --json

genreplay evidence "$REPLAY_TX" \
  --network testnet-bradbury \
  --output evidence/replay-case \
  --json
```

For direct transaction-level replay:

```bash
genreplay replay \
  evidence/replay-case/incident.genreplay \
  --receipt-current \
  --network testnet-bradbury \
  --json
```

## CI evidence

The workflow file is:

```text
.github/workflows/live-evidence.yml
```

Its gate requires:

- the official SDK-control transaction to produce an intact real capsule;
- the replay transaction to produce an intact real capsule;
- at least one consensus round in each evidence case;
- at least one successful validator-mode replay for the replay case;
- deep `doctor` to report validator replay availability.

A failed public RPC call, missing leader evidence, or failed `gen_call` does not get converted into a passing result.

The exact successful run ID, final commit SHA, capsule SHA-256, and artifact digest are recorded here after the release candidate reaches a fully green head. Until those values are present, this document should not be read as claiming that the final v0.2 release gate has passed.

## Offline verification

The normal CI matrix independently verifies Python 3.11, 3.12, and 3.13 with:

```text
package installation
Ruff
full pytest suite
compileall
CLI smoke tests
public Python API imports
wheel construction
```

## Evidence limitations

- A public historical replay cannot recover private validator credentials, hidden provider changes, or external HTTP/LLM payloads never published by the protocol.
- Validator-mode `gen_call` is not itself a fresh network consensus round.
- The source RPC remains part of the trust boundary. Capsule hashing proves integrity after capture, not source-node honesty.
- Public networks may later prune historical debug/state surfaces. The committed workflow and uploaded artifacts exist to preserve what was verifiable at the release point.
