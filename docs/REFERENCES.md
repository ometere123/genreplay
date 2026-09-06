# Upstream GenLayer References

GenReplay's v0.1 protocol assumptions were checked against the current GenLayer documentation on 2026-09-06.

These links are engineering references, not copied specifications. If an upstream RPC changes, update GenReplay's fixtures/tests and document the compatibility change.

## Node/RPC

- Transaction receipt: https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getTransactionReceipt
- Transaction lifecycle: https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getTransactionLifecycle
- `gen_call`: https://docs.genlayer.com/api-references/genlayer-node/gen/gen_call
- Node debug API / trace transaction: https://docs.genlayer.com/api-references/genlayer-node
- Contract code: https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getContractCode
- Contract state: https://docs.genlayer.com/api-references/genlayer-node/gen/gen_getContractState

## Consensus semantics

- Transaction statuses: https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/transactions/transaction-statuses
- Transaction execution: https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/transactions/transaction-execution
- Appeals: https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/optimistic-democracy/appeal-process
- Validators and roles: https://docs.genlayer.com/understand-genlayer-protocol/core-concepts/validators-and-validator-roles
- Equivalence Principle: https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle

## Developer tooling

- GenLayer Test: https://docs.genlayer.com/api-references/genlayer-test
- Direct Mode validator testing: https://docs.genlayer.com/api-references/genlayer-test/direct
- GenLayerPY: https://docs.genlayer.com/api-references/genlayer-py
- GenLayer CLI: https://docs.genlayer.com/api-references/genlayer-cli

## Networks

- Current networks and RPCs: https://docs.genlayer.com/developers/networks
- Consensus v0.6 migration / Studio-dev release family: https://docs.genlayer.com/developers/consensus-v06-migration

## Important upstream facts used by GenReplay

1. `gen_getTransactionReceipt` exposes `roundData`, committee addresses, leader index, vote/result hashes, `randomSeed`, `txCallData`, `eqBlocksOutputs`, and read-state block ranges.
2. `gen_dbg_traceTransaction` exposes per-round GenVM execution diagnostics and `eq_outputs`.
3. `gen_call` accepts `leader_results`; when provided, GenVM runs the validator path instead of the leader path for nondeterministic calls.
4. Stored consensus status is not equivalent to successful contract execution.
5. Advanced lifecycle projection is separate from stored status, and a `Finalize` resolution action is not a synthetic stored `ReadyToFinalize` state in the current v0.6 model.
6. Studio-dev is a distinct chain/environment from stable Studionet and must not be treated as an alias at the RPC/SDK layer.
