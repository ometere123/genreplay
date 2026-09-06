# Evidence Bundle Integrity

`genreplay evidence` produces a reviewer-oriented directory around one real GenLayer transaction. The bundle is deliberately separate from the `.genreplay` capsule: the capsule preserves protocol evidence, while the surrounding bundle adds derived analysis, replay attempts, deterministic explanations, and reviewer-facing metadata.

## Layout

A replay-enabled bundle can contain:

```text
evidence.json
incident.genreplay
integrity.json
analysis.json
timeline.json
explanation.json
capture-issues.json
replays/
  round-000.json
  round-001.json
  ...
  receipt-current.json
```

`evidence.json` is the bundle manifest. Its `artifact_integrity` object commits every generated artifact except `evidence.json` itself by:

```json
{
  "timeline.json": {
    "sha256": "...",
    "size": 1234
  }
}
```

The nested `incident.genreplay` capsule keeps its own independent manifest and SHA-256 checks.

## Offline verification

Verification does not require a wallet, GenLayer RPC, LLM provider, or internet connection:

```python
from genreplay import GenReplay

client = GenReplay("https://rpc-bradbury.genlayer.com")
report = client.verify_evidence("evidence/replay-case")
assert report["ok"]
```

`verify_evidence` checks:

1. evidence schema version;
2. every manifest-listed artifact path remains inside the evidence directory;
3. every artifact exists;
4. SHA-256 matches;
5. byte length matches;
6. the nested `.genreplay` capsule independently passes its own integrity validation.

A modified derived report such as `timeline.json` therefore fails evidence verification even if the original capsule remains intact.

## Trust boundary

This integrity layer proves that a captured evidence directory has not changed after its manifest was written. It does **not** prove that the source RPC was honest when the transaction was captured.

For high-assurance forensic work, independently operated source nodes or signed provenance can be layered above this format in a future release.

## Why `evidence.json` does not hash itself

Self-hashing would be recursively unstable. The manifest is instead the root description of the bundle. Reviewers who require a single external commitment can hash or sign `evidence.json` itself after generation.
