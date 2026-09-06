# Architecture

## Design goal

GenReplay preserves enough protocol-visible material to turn a GenLayer consensus incident into a repeatable engineering experiment without pretending that nondeterministic history is magically deterministic.

## Trust boundaries

### Source RPC

`capture` trusts the selected GenLayer RPC to return the transaction receipt, lifecycle, traces and historical contract data. GenReplay records the endpoint and chain ID in the capsule so consumers know where the evidence came from.

GenReplay does not sign transactions during capture or replay. `gen_call` is a non-transactional execution surface.

### Capsule

The capsule is a ZIP archive with a canonical JSON manifest. Every payload entry is committed by SHA-256 and byte length. The manifest itself is outside its own digest set to avoid recursive hashing.

The digest proves internal integrity after capture; it does **not** by itself prove that the source RPC told the truth. Stronger provenance can be layered on top by signing the capsule hash or retaining independent captures from multiple nodes.

### Replay RPC

A replay may intentionally target a different node, chain, contract address or historical block. Therefore replay output is always reported separately from captured history.

## Capture pipeline

1. Validate 32-byte transaction ID.
2. Fetch `gen_getTransactionReceipt` (required).
3. Fetch chain ID (best effort).
4. Fetch `gen_getTransactionLifecycle` (best effort).
5. Discover round numbers from `roundData`.
6. Fetch `gen_dbg_traceTransaction` per round (best effort).
7. Identify a historical state block from `readStateBlockRanges`.
8. Fetch historical contract source with `gen_getContractCode` (best effort, with fallbacks).
9. Decode and SHA-256 hash the source.
10. Generate schema from the captured base64 source with `gen_getContractSchema`.
11. Fetch contract state at the historical block when available.
12. Produce a consensus-aware analysis summary.
13. Record every non-fatal capture gap.
14. Commit all payloads in the manifest and write a deterministic ZIP layout.

Only the receipt is mandatory. Optional RPC failures do not destroy otherwise useful evidence.

## Replay pipeline

For round `R`:

1. Load and integrity-check the capsule.
2. Load the historical receipt and round trace.
3. Extract trace `eq_outputs`.
4. Build a `gen_call` request using the captured sender, recipient, call data and historical state block.
5. Supply the `eq_outputs` as `leader_results`.
6. GenVM executes validator mode on the target RPC.
7. Preserve the raw response and derive a compact replay signature.

The signature is diagnostic, not a synthetic consensus vote. It records GenVM status, the reported nondeterministic disagreement call number, return data presence and emitted message/event counts.

## Counterfactuals

A replay scenario is portable JSON and may override:

- target contract address;
- sender;
- call data;
- accepted/finalized state view;
- block number;
- RPC environment;
- leader result list.

This makes it possible to test a historical proposal against another deployed contract revision or another GenLayer environment without modifying the original capsule.

## Minimization

`minimize` is deliberately narrow. Equivalence outputs are protocol-encoded opaque bytes. GenReplay does not interpret or fuzz their internal encoding.

Instead, it executes shorter ordered prefixes and accepts a reduction only if the target replay signature is exactly reproduced. Failed or erroring candidates are retained in the trial log as evidence.

## Why raw RPC rather than genlayer-py?

The SDK is excellent for application development, but a replay/debugging tool benefits from keeping the exact RPC objects used by the consensus node. Direct RPC access also avoids coupling capsule fidelity to SDK normalization choices. The package has no mandatory third-party runtime dependencies.

## Extension points

Future versions can add adapters without changing capsule v1 semantics:

- full instrumented web/LLM response capture in local development;
- multi-node capture quorum and signed provenance;
- triggered child-transaction graph capture;
- validator configuration fingerprints;
- appeal round experimentation;
- local GenVM runner adapters;
- semantic diff plugins for known equivalence encodings.
