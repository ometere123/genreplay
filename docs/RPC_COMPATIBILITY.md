# RPC Compatibility

GenReplay targets the current GenLayer node API and degrades explicitly when optional development/debug endpoints are unavailable.

## Built-in networks

| Name | RPC | Chain ID | Use |
|---|---|---:|---|
| `studionet` | `https://studio.genlayer.com/api` | 61999 | Stable hosted development |
| `studio-dev` | `https://studio-dev.genlayer.com/api` | 61997 | Consensus release-candidate preview |
| `localnet` | `http://localhost:4000/api` | 61127 | Local Studio/GLSim |
| `testnet-bradbury` | `https://rpc-bradbury.genlayer.com` | 4221 | Production-like testnet |
| `testnet-asimov` | `https://rpc-asimov.genlayer.com` | 4221 | Infrastructure/stress testnet |

Use `--rpc` for custom nodes.

## Methods

### Required for capture

`gen_getTransactionReceipt`

Without a receipt there is no protocol capsule.

### Best-effort capture enrichment

```text
eth_chainId
gen_getTransactionLifecycle
gen_dbg_traceTransaction
gen_getContractCode
gen_getContractState
gen_getContractSchema
```

A missing optional method or unavailable historical view becomes an entry in `capture/issues.json`.

### Required for validator replay

`gen_call` with substantive `leader_results`.

Supplying leader equivalence outputs switches GenVM into the validator path. GenReplay refuses to invoke validator replay when the available protocol evidence contains no substantive leader result.

## Leader-result evidence sources

### Per-round trace

Preferred when available:

```text
gen_dbg_traceTransaction(tx, round=N)
  -> eq_outputs
```

This evidence is explicitly round-attributed.

### Transaction receipt

Bradbury/testnet receipts may expose:

```text
eqBlocksOutputs
```

This is an RLP-encoded transaction-level field. GenReplay 0.2 decodes it according to the protocol tooling format and removes the final `padded` sentinel.

For multi-round history, this field is **not** assigned to a specific round. Replay uses `round_number = null` and explicit transaction-level provenance.

## Live Bradbury findings

Submission hardening deliberately exercised the public Bradbury RPC instead of assuming Studio and testnet return identical shapes.

Observed differences include:

- receipts can expose numeric `status` and `txExecutionResult` without their optional name fields;
- `gen_getTransactionLifecycle` may be unavailable on the public endpoint for historical transactions;
- historical code/state can be available for one transaction while unavailable for another;
- a debug trace can be available yet expose an empty `eq_outputs` list;
- substantive transaction-level `eqBlocksOutputs` can exist even when historical per-round traces expose no equivalence outputs;
- a receipt can contain padding-only `eqBlocksOutputs`, which is not replay evidence.

GenReplay therefore normalizes numeric v0.6 enums while preserving the raw receipt, and it keeps capture/replay capability reporting transaction-specific.

## Consensus v0.6 status model

The current testnet status codes include:

```text
5  ACCEPTED
6  UNDETERMINED
7  FINALIZED
11 READY_TO_FINALIZE
12 VALIDATORS_TIMEOUT
13 LEADER_TIMEOUT
```

GenReplay retains the raw numeric code and derives a human-readable name when `statusName` is absent.

Execution result codes are handled independently. For example:

```text
1 FINISHED_WITH_RETURN
2 FINISHED_WITH_ERROR
3 TIMEOUT
4 NONDET_DISAGREE
```

A receipt with `status = 7` and `txExecutionResult = 2` is therefore **Finalized but not successful**.

## Development/debug endpoint availability

Public/shared networks may:

- expose fewer debug surfaces than Localnet/Studio;
- rate-limit calls;
- prune historical state;
- differ in receipt field naming/normalization;
- retain transaction-level proposal bytes without round-level debug bytes.

GenReplay records these as evidence limitations and never fabricates missing history.

Use:

```bash
genreplay doctor --network testnet-bradbury --tx-id 0x... --json
```

to test actual transaction-specific compatibility rather than relying on static endpoint assumptions.

## Schema generation

`gen_getContractSchema` accepts base64 contract code. GenReplay derives schema from the exact captured code bytes when available, avoiding accidental source/schema drift.
