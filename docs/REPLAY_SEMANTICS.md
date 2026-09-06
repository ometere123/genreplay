# Replay Semantics

## Two different meanings of replay

The word "replay" is easy to overstate in an AI-driven consensus system. GenReplay uses it precisely.

### Protocol replay (v1)

Given a captured leader's `eq_outputs`, run the same call in GenVM validator mode by passing those outputs to `gen_call.leader_results`.

This answers:

> How does the validator path on this target RPC/contract/state react to this captured leader proposal?

It does not answer:

> What exact private tokens, web bytes and model configuration did every historical validator observe?

Those inputs are not guaranteed to be present in the public transaction interfaces.

### Full nondeterminism replay (future/instrumented)

A development harness could intentionally record raw web/LLM requests and responses, model/provider configuration and other nondeterministic inputs. That is a different capture level and should be marked explicitly.

## Historical state

Capture chooses the first useful `ProcessingBlock`, then `ProposalBlock`, then `ActivationBlock` from `readStateBlockRanges`. Contract source/state requests prefer that block and fall back to current accepted/finalized views when a backend cannot serve historical data.

Every fallback is recorded as a capture issue rather than hidden.

## Status is not success

GenReplay's `successful` flag requires:

- consensus status `Accepted` or `Finalized`; and
- execution result `FinishedWithReturn`.

Consequently:

- `Finalized + FinishedWithError` is not successful;
- `Accepted + Timeout` is not successful;
- `Undetermined` is not successful.

## Validator replay result

`gen_call` returns execution status and, in validator mode, `nondetDisagreementCallNo` when a nondeterministic equivalence check disagrees.

GenReplay exposes that value directly. It does not turn absence of a disagreement number into a claim that an entire historical committee would have voted identically.

## Counterfactual target contracts

A scenario can target another deployed contract address. This is the supported v1 path for testing a historical leader proposal against patched code. GenReplay does not pretend it can replace code at an arbitrary historical address.

For local development, deploy the candidate contract to Localnet/Studio and point the scenario at that address. Clear the original block pin with `--latest-state` if the candidate did not exist at the captured block.

## Minimization semantics

The exact replay signature is:

- GenVM status code;
- status message;
- nondeterministic disagreement call index;
- returned data;
- whether stderr is present;
- emitted event count;
- emitted message count.

A prefix reduction is kept only when all signature fields match the baseline.
