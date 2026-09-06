# Submission Evidence

GenReplay is pure GenLayer developer infrastructure. It has no project-owned Intelligent Contract, frontend, browser wallet flow, or centralized AI decision service. The evidence below proves the tool against **real GenLayer protocol data**, not only fixture-driven tests.

## Evidence standard

A submission-grade GenReplay proof establishes all of the following independently:

1. a real GenLayer transaction can be captured;
2. the `.genreplay` capsule passes integrity verification;
3. consensus status and contract execution result are reported separately;
4. available committee/round history is preserved;
5. missing RPC evidence is recorded explicitly rather than fabricated;
6. validator-mode replay occurs only when substantive `leader_results` evidence exists;
7. replay evidence states whether it is round-attributed or transaction-level;
8. machine-readable evidence can be reproduced by CI.

The `live-evidence` GitHub workflow enforces these properties on public Bradbury data and uploads the evidence directory even when a gate fails.

## Certified live run

The submission-hardening implementation was certified by a fully successful `live-evidence` workflow:

```text
workflow run       34004547147
implementation SHA a1e3aa0445fb514ad60cc433c715ae8e4881687b
artifact ID        9980531505
artifact name      genreplay-bradbury-live-proof
artifact SHA-256   4eed3574114b0caf6fa659fccda4d8c6e035a3208e8024e46c5001353c11fc2e
conclusion         success
```

A compact immutable record of the certified outputs is committed at:

```text
evidence/bradbury-v0.2.json
```

The documentation/evidence-record commits made after the certified implementation do not change the runtime logic exercised by that run.

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

This transaction is used by GenLayer's JavaScript SDK smoke tests. The certified GenReplay capture established:

```text
capsule SHA-256  ec22e1a8bade952f4c6e88ecb8c4855f0669d36d5481d2898da8ff180dfd5129
integrity        PASS
status           FINALIZED
execution        FINISHED_WITH_ERROR
successful       false
round count      1
capture gaps     3
```

The public debug trace is available but exposes no substantive `eq_outputs`. Receipt `eqBlocksOutputs` decodes to the protocol padding sentinel only.

GenReplay therefore **refuses to manufacture validator replay evidence** from this transaction.

This negative control proves two important behaviors:

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

The certified capture established:

```text
capsule SHA-256        85bffd6a59f4bdb1d945a971701bbcf99d36e3af50dc33c18b2e1d1614496c16
integrity              PASS
capture files          13
capture gaps           1
status                 FINALIZED
execution result       NOT_VOTED
receipt round records  7
captured trace rounds  0, 1, 2, 3, 4
historical source      captured
historical state       captured
```

The transaction contains multi-round/appeal-style history with changing committee sizes and outcomes. Its transaction-level `eqBlocksOutputs` contains one substantive stored result rather than only padding.

The public per-round debug traces are present but do not expose historical `eq_outputs`, so five round-attributed replay attempts correctly remain failed evidence rather than being silently rewritten.

### Successful validator replay

GenReplay then decoded the transaction-level stored proposal and ran it through real Bradbury `gen_call` validator mode.

Evidence:

```text
replay attempts        6
successful             1
failed                 5
successful source      receipt.eqBlocksOutputs
round attributed       false
scenario round_number  null
leader-results count   1
```

Captured leader result:

```text
0x008c017b226f7574636f6d65223a22594553227d
```

Validator replay signature:

```json
{
  "status_code": 0,
  "status_message": "success",
  "nondet_disagreement_call": null,
  "return_data": "00",
  "stderr_present": false,
  "event_count": 0,
  "message_count": 0
}
```

Deep doctor result:

```text
grade                              REPLAY_READY_PARTIAL_CAPTURE
validator_replay                   available
validator_replay_source            receipt.eqBlocksOutputs
validator_replay_round_attributed  false
```

The scenario provenance stored with the successful replay is:

> Validator-mode replay leader_results source: transaction-level receipt.eqBlocksOutputs; this evidence is intentionally not attributed to a specific consensus round.

That provenance is part of the machine-readable replay artifact.

## Why this case changed GenReplay 0.2

The public receipt exposes transaction-level equivalence output bytes but does not bind those bytes to a specific historical round. GenReplay therefore defines two separate replay concepts.

**Round-attributed replay**

```text
trace round N -> eq_outputs -> round_number = N
```

**Transaction-level stored-proposal replay**

```text
receipt eqBlocksOutputs -> leader_results -> round_number = null
```

The second mode never claims that the stored receipt output came from round 0, round 1, or another specific historical round.

That distinction is enforced in code, JSON output, evidence metadata, tests, CLI behavior, and the certified live proof.

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

## CI gate

Workflow:

```text
.github/workflows/live-evidence.yml
```

The gate requires:

- the official SDK-control transaction to produce an intact real capsule;
- the replay transaction to produce an intact real capsule;
- at least one consensus round in each evidence case;
- at least one successful validator-mode replay for the replay case;
- deep `doctor` to report validator replay availability.

A failed public RPC call, missing leader evidence, or failed `gen_call` does not get converted into a passing result.

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

The certified implementation SHA passed all three matrix jobs before the live-evidence gate was stamped.

## Evidence limitations

- A public historical replay cannot recover private validator credentials, hidden provider changes, or external HTTP/LLM payloads never published by the protocol.
- Validator-mode `gen_call` is not itself a fresh network consensus round.
- The source RPC remains part of the trust boundary. Capsule hashing proves integrity after capture, not source-node honesty.
- Public networks may later prune historical debug/state surfaces. The certified proof record preserves what was verifiable at the release point.
