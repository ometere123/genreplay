# GenReplay Capsule Specification v1

## Media type and extension

Recommended extension: `.genreplay`

Physical container: ZIP (DEFLATE)

Logical format identifier: `genreplay-capsule`

Version: `1`

## `manifest.json`

Canonical UTF-8 JSON with fields:

```json
{
  "format": "genreplay-capsule",
  "version": 1,
  "tool_version": "0.1.0",
  "captured_at": "2026-09-06T00:00:00Z",
  "tx_id": "0x...",
  "capture_level": "protocol",
  "network": {
    "rpc_url": "https://studio.genlayer.com/api",
    "chain_id": 61999,
    "preset": "studionet",
    "historical_state_block": "0x..."
  },
  "files": {
    "transaction/receipt.json": {
      "sha256": "...",
      "size": 1234
    }
  }
}
```

`files` commits every payload entry except `manifest.json` itself.

## Required payload

`transaction/receipt.json`

This is the raw object returned by `gen_getTransactionReceipt` at capture time.

`analysis/summary.json`

Derived diagnostics. It is evidence about the capture, not a replacement for the raw receipt.

`capture/issues.json`

Array of capture gaps. Empty is valid.

## Optional payloads

### `transaction/lifecycle.json`

Raw advanced lifecycle snapshot from `gen_getTransactionLifecycle`.

### `traces/round-NNN.json`

Raw `gen_dbg_traceTransaction` response for a consensus round.

### `contract/source.b64`

Base64 source returned by `gen_getContractCode`.

### `contract/source.py`

Decoded bytes from `source.b64`. The `.py` name reflects today's Intelligent Contract source format; consumers must not assume it is trustworthy merely because it parses as Python.

### `contract/source.sha256`

SHA-256 digest of decoded contract source.

### `contract/schema.json`

Schema derived from the captured base64 code by `gen_getContractSchema`.

### `contract/state.hex`

Raw state snapshot returned by `gen_getContractState` at the chosen historical block/status.

## Capture levels

v1 defines:

- `protocol`: network-visible receipt/lifecycle/trace/source/state evidence.

Future versions may define an instrumented level that intentionally records raw nondeterministic web/LLM inputs during development. A `protocol` capsule must never imply those private inputs were captured.

## Deterministic archive writing

GenReplay writes entries in sorted path order with a fixed ZIP timestamp. The manifest includes the real capture time. This produces stable archive bytes for the same logical payload and manifest.

## Integrity

Consumers MUST reject a capsule when:

- `format` is unknown;
- `version` is unsupported;
- a declared file is absent;
- SHA-256 differs;
- declared byte size differs.

A capsule signature is intentionally outside v1. Signing can be introduced as a separate provenance layer without invalidating existing archives.
