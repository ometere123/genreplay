# Contributing

GenReplay is protocol tooling. Changes should favor evidence fidelity over convenience.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check .
```

## Rules

1. Never infer consensus success from status alone.
2. Preserve raw RPC responses whenever a normalized view is also produced.
3. Record missing evidence; do not silently substitute fabricated values.
4. Treat equivalence outputs as opaque unless an upstream public format is explicitly versioned.
5. New capsule fields must be backwards-compatible or require a capsule-format version bump.
6. Network-changing behavior requires a separate explicit design review. v1 is intentionally read-only.
7. Add tests for every RPC shape or replay assumption changed.

## Pull requests

Describe:

- the GenLayer protocol surface touched;
- the source/documentation or fixture that establishes its shape;
- failure behavior on older/partial RPCs;
- capsule compatibility impact;
- tests added.
