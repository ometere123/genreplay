# Testing Strategy

GenReplay is infrastructure that interprets protocol evidence. Tests therefore focus on preventing silent evidence corruption and semantic overclaiming.

## Offline suite

Run:

```bash
pytest -q
```

The suite does not require Docker, a wallet, an LLM provider, or a GenLayer network.

Coverage areas:

- current built-in network identities;
- raw JSON-RPC envelope handling and error propagation;
- exact GenLayer parameter names (`txId` versus debug `txID`);
- capture of multiple consensus rounds;
- partial/pruned debug trace handling;
- historical state block selection;
- contract source/schema/state capture;
- SHA-256 capsule integrity and tamper rejection;
- deterministic capsule serialization;
- consensus status versus execution-success rules;
- nondeterministic disagreement diagnostics;
- validator-mode `leader_results` construction;
- refusal to call a leader-only execution a validator replay;
- conservative prefix minimization;
- structural capsule diffs;
- portable pytest regression export;
- CLI smoke paths.

## Packaging checks

```bash
python -m compileall -q genreplay tests
python -m pip wheel . --no-deps --no-build-isolation -w dist-test
python -m genreplay --version
python -m genreplay networks
```

## Lint

```bash
ruff check .
```

GitHub Actions runs lint and tests on Python 3.11, 3.12 and 3.13.

## Live integration test plan

Live checks are intentionally not required for ordinary CI because public development RPCs can reset, rate-limit, or prune debugging data.

Before a release candidate:

1. Select a known transaction on Localnet or Studionet.
2. Run `genreplay doctor` against the endpoint.
3. Capture it with traces, code and state enabled.
4. Verify the capsule.
5. Compare captured round count with the network receipt.
6. Replay round 0 in validator mode.
7. Export a scenario and replay it unchanged.
8. Deploy a patched candidate contract to Localnet.
9. Fork the scenario to the candidate address with `--latest-state`.
10. Confirm the changed validator behavior is represented by the replay signature.
11. Export the incident as a pytest regression.
12. Run the exported test with `GENREPLAY_RPC` set.

## Failure injection

The offline fake RPC deliberately supports partial failures. New capture surfaces should include tests where:

- method is unsupported;
- history is pruned;
- response type is malformed;
- JSON-RPC error includes a code/data payload;
- one round succeeds and another fails.

A best-effort capture must remain inspectable whenever the required receipt was captured.
