# RPC Compatibility

GenReplay targets the current GenLayer node API and degrades gracefully when optional development/debug endpoints are unavailable.

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

Without a receipt there is no capsule.

### Best-effort capture enrichment

`eth_chainId`

`gen_getTransactionLifecycle`

`gen_dbg_traceTransaction`

`gen_getContractCode`

`gen_getContractState`

`gen_getContractSchema`

A missing optional method becomes an entry in `capture/issues.json`.

### Required for validator replay

`gen_call` with `leader_results`.

The current node API defines `leader_results` as an array of hex-encoded equivalence outputs from a leader execution. Supplying it switches GenVM into validator mode.

## Development-debug endpoint availability

Public/shared networks may expose fewer debug surfaces than Localnet or Studio, may rate-limit calls, or may prune historical state. GenReplay treats those as evidence limitations, not reasons to fabricate missing data.

## Consensus v0.6 status model

The v0.6 protocol separates stored status from lifecycle projection. `resolutionAction: Finalize` is an action, not a synthetic `ReadyToFinalize` stored status. GenReplay preserves the lifecycle object verbatim and warns when finalization is available but not yet materialized.

## Schema generation

Current `gen_getContractSchema` accepts base64 contract code. GenReplay intentionally derives schema from the same captured code bytes, avoiding accidental schema/source drift.
