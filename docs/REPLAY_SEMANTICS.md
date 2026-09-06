# Replay Semantics

The word **replay** is easy to overstate in an AI-driven consensus system. GenReplay uses it narrowly and records the provenance of every leader-result input.

## Protocol replay

Given protocol-visible leader equivalence outputs, GenReplay reruns the historical call through GenVM validator mode by supplying those outputs as `gen_call.leader_results`.

This answers:

> How does the validator path on this target RPC/contract/state react to this captured leader proposal?

It does **not** answer:

> What exact private tokens, external web bytes, hidden provider state, or model configuration did every historical validator observe?

Those private inputs are not guaranteed to be public transaction evidence.

## Two provenance classes

GenReplay 0.2 distinguishes two forms of protocol-visible leader evidence.

### Round-attributed trace replay

When `gen_dbg_traceTransaction` for round `N` exposes substantive `eq_outputs`, the replay scenario records:

```json
{
  "round_number": 0,
  "leader_results": ["0x..."]
}
```

and its notes state that `leader_results` came from that round's trace.

This is the strongest historical attribution because the debug call itself is round-scoped.

CLI:

```bash
genreplay replay incident.genreplay --round 0
```

### Transaction-level stored-proposal replay

Bradbury/testnet receipts may expose `eqBlocksOutputs` even when historical per-round debug traces omit `eq_outputs`.

GenLayer protocol tooling encodes this field as an RLP list of equivalence outputs plus a final `b"padded"` accounting sentinel. GenReplay decodes the list, strips only a final exact padding sentinel, and rejects an empty/padding-only result.

For a **single-round** transaction, the transaction-level result is unambiguous enough to serve as a compatibility fallback for that one round.

For **multi-round** history, GenReplay never guesses which historical round produced the stored transaction-level bytes. Instead it creates a distinct scenario:

```json
{
  "round_number": null,
  "leader_results": ["0x..."]
}
```

and records:

```text
transaction-level receipt.eqBlocksOutputs; not attributed to a specific consensus round
```

CLI:

```bash
genreplay replay incident.genreplay --receipt-current
```

This distinction prevents a transaction-level protocol field from being mislabeled as round-0 or appeal-round evidence.

## RLP safety

The built-in `eqBlocksOutputs` decoder is dependency-free and deliberately narrow. It:

- accepts protocol hex with or without `0x`;
- requires canonical top-level RLP list structure;
- rejects truncated/non-canonical RLP;
- rejects nested lists for this field;
- strips `b"padded"` only when it is the final exact item;
- returns the remaining byte strings as `0x`-prefixed `leader_results`.

GenReplay does not attempt to semantically parse the contents of each equivalence output unless a future stable protocol codec explicitly defines that layer.

## Full nondeterminism replay

Full historical nondeterminism replay is a different problem. A development harness could intentionally record raw web/LLM requests and responses, provider/model configuration, GenVM time inputs, and other nondeterministic data at execution time.

That would require a different capture level. A v1 `protocol` capsule never implies those private inputs were recorded.

## Historical state

Capture chooses the first useful `ProcessingBlock`, then `ProposalBlock`, then `ActivationBlock` from `readStateBlockRanges`. Contract source/state reads prefer that historical block and can fall back to accepted/finalized current views when the backend cannot serve the preferred history.

Every fallback is recorded in `capture/issues.json`.

A counterfactual against a newly deployed contract can clear the historical block with:

```bash
genreplay replay incident.genreplay --receipt-current --target 0x... --latest-state
```

The context change is explicit because the new contract may not have existed at the original block.

## Consensus status is not execution success

GenReplay normalizes both named and numeric v0.6/testnet receipt enums.

The `successful` flag requires:

- consensus status `Accepted` or `Finalized`; and
- execution result `FinishedWithReturn`.

Consequently:

```text
FINALIZED + FINISHED_WITH_ERROR    -> not successful
ACCEPTED  + TIMEOUT                -> not successful
UNDETERMINED                       -> not successful
```

A completed consensus lifecycle can therefore coexist with a failed contract execution.

## Validator replay output

`gen_call` returns execution status and may expose `nondetDisagreementCallNo` during validator-mode disagreement.

GenReplay preserves the raw response and derives a compact diagnostic signature. The absence of a disagreement number is **not** converted into a claim that the historical stake-weighted committee would have voted identically.

`gen_call` replay is execution of the validator path. It is not a new blockchain transaction and does not itself assemble a committee, perform commit/reveal voting, or finalize consensus.

## Counterfactual target contracts

A replay scenario can target another deployed contract address. This is the supported path for testing historical leader evidence against patched code.

GenReplay does not pretend a remote node can replace arbitrary historical code. Deploy candidate code to Localnet/Studio or another suitable environment and set an explicit alternate target.

## Minimization semantics

Equivalence outputs are treated as opaque protocol bytes. GenReplay never flips arbitrary bytes and labels the result a valid counterexample.

The minimizer only tests shorter ordered prefixes through actual validator-mode `gen_call`. A reduction is retained only when the complete replay signature matches the baseline:

- GenVM status code;
- status message;
- nondeterministic disagreement call index;
- returned data;
- whether stderr is present;
- emitted event count;
- emitted message count.

Every trial is retained as evidence.
