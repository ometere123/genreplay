# GenReplay Capsule Specification v1

GenReplay 0.2 keeps the logical capsule format at version `1`. The submission-hardening release tightens the **reader security contract** without changing the stored schema.

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
  "tool_version": "0.2.0",
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

### `transaction/receipt.json`

Raw object returned by `gen_getTransactionReceipt` at capture time. Transaction-level `eqBlocksOutputs`, when exposed by the network, remain preserved here exactly as returned.

### `analysis/summary.json`

Derived diagnostics. This is an interpretation layer and never replaces the raw receipt.

### `capture/issues.json`

Array of capture gaps/fallbacks. Empty is valid. Missing optional RPC evidence must be represented here rather than silently invented.

## Optional payloads

### `transaction/lifecycle.json`

Raw advanced lifecycle snapshot from `gen_getTransactionLifecycle` when supported by the endpoint.

### `traces/round-NNN.json`

Raw `gen_dbg_traceTransaction` response for a consensus round.

A trace can exist without exposing substantive `eq_outputs`. The presence of the file alone does not make that round replayable.

### `contract/source.b64`

Base64 source returned by `gen_getContractCode`.

### `contract/source.py`

Decoded bytes from `source.b64`. The `.py` name reflects the current Intelligent Contract source form; consumers must not trust it merely because it parses as Python.

### `contract/source.sha256`

SHA-256 digest of decoded contract source.

### `contract/schema.json`

Schema derived from the captured base64 code by `gen_getContractSchema`.

### `contract/state.hex`

Raw state snapshot returned by `gen_getContractState` at the chosen historical block/status.

## Capture levels

v1 defines:

- `protocol`: protocol-visible receipt/lifecycle/trace/source/state evidence.

Future versions may define an instrumented capture level that intentionally records raw nondeterministic web/LLM inputs during development. A `protocol` capsule must never imply those private inputs were recorded.

## Deterministic archive writing

GenReplay writes entries in sorted path order with a fixed ZIP member timestamp. Real capture time belongs in the manifest. Identical logical payload + manifest therefore produces stable archive bytes.

## Integrity contract

Consumers MUST reject a capsule when:

- `format` is unknown;
- `version` is unsupported;
- `manifest.json` is missing or invalid;
- a declared file is absent;
- an undeclared payload exists;
- declared size differs from ZIP-reported uncompressed size;
- SHA-256 differs.

The SHA-256 set proves internal post-capture integrity. It does **not** prove the source RPC returned truthful chain history.

## Untrusted ZIP security boundary

`.genreplay` is forensic input and MUST be treated as untrusted.

The reference v0.2 reader rejects before loading arbitrary payloads when any of these conditions occur:

```text
duplicate ZIP member name
absolute path
backslash path
empty / dot / parent-traversal path component
undeclared payload
missing declared payload
reserved manifest path used as payload
manifest larger than 1 MiB
more than 512 declared payload files
individual payload larger than 32 MiB
total declared uncompressed payload larger than 128 MiB
manifest size that disagrees with the ZIP entry
```

Normal `Capsule.load` does not extract entries to filesystem paths. It reads only manifest-declared payloads after validating the archive structure and declared sizes.

These limits are implementation safety limits for capsule v1, not evidence claims about GenLayer transaction maximums.

## Replay provenance is outside the capsule payload schema

Replay outputs are generated artifacts, not mutations of the source capsule. A replay scenario records `round_number` separately:

- integer: evidence attributed to a concrete trace round;
- `null`: transaction-level receipt evidence intentionally not attributed to a historical round.

See [`REPLAY_SEMANTICS.md`](REPLAY_SEMANTICS.md).

## Signatures

Artifact signing is intentionally outside capsule v1. A future signature layer can sign the capsule digest without invalidating existing v1 archives.
