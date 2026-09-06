# Limitations and Non-Goals

## Historical validators are not virtual machines in a bottle

A protocol capsule captures what the node exposes. It cannot reconstruct private validator provider credentials, hidden model updates or raw external responses that were never published.

## Replay is read-only execution, not a new consensus round

`gen_call` validator mode executes the validator path against supplied leader outputs. It does not assemble a new stake-weighted committee, commit/reveal votes or create a blockchain transaction.

## Candidate code must be executable somewhere

v1 counterfactual source testing targets another deployed address. GenReplay does not replace deployed code in an arbitrary remote node. Deploy candidate code to Localnet/Studio, then set `--target`.

## `txCallData` decoding

v1 preserves and reuses encoded call data rather than implementing a separate GenLayer calldata codec. This reduces the risk of re-encoding a historical call incorrectly.

## Equivalence output internals

GenReplay treats each equivalence output as opaque hex. It does not guess at private or unstable serialization formats.

## Historical source/state

RPCs may prune history or not expose debug endpoints. Capture fallbacks are recorded in `capture/issues.json`.

## Appeal simulation

v1 captures appeal rounds when they appear in `roundData`, but it does not claim to predict future appeal committees. Empirical committee simulation belongs in a separate research layer.
