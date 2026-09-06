from __future__ import annotations

from pathlib import Path
from typing import Any

from .capture import CaptureService
from .replay import ReplayEngine, scenario_from_capsule
from .report import build_timeline, explain_capsule
from .util import pretty_json, sha256_bytes

EVIDENCE_SCHEMA_VERSION = 1


class EvidenceService:
    """Generate a reviewer-friendly evidence bundle from one real GenLayer transaction."""

    def __init__(self, rpc: Any):
        self.rpc = rpc

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pretty_json(value), encoding="utf-8")

    def generate(
        self,
        tx_id: str,
        output_dir: str | Path,
        *,
        include_contract: bool = True,
        include_state: bool = True,
        replay_rounds: bool = True,
    ) -> dict[str, Any]:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        capsule = CaptureService(self.rpc).capture(
            tx_id,
            include_traces=True,
            include_contract=include_contract,
            include_state=include_state,
        )
        capsule_path = root / "incident.genreplay"
        capsule.write(capsule_path)

        integrity = capsule.verify_integrity()
        timeline = build_timeline(capsule)
        explanation = explain_capsule(capsule)
        issues = (
            capsule.read_json("capture/issues.json") if capsule.has("capture/issues.json") else []
        )
        analysis = (
            capsule.read_json("analysis/summary.json") if capsule.has("analysis/summary.json") else {}
        )

        self._write_json(root / "integrity.json", integrity)
        self._write_json(root / "timeline.json", timeline)
        self._write_json(root / "explanation.json", explanation)
        self._write_json(root / "capture-issues.json", issues)
        self._write_json(root / "analysis.json", analysis)

        replay_results: list[dict[str, Any]] = []
        if replay_rounds:
            engine = ReplayEngine(self.rpc)
            for round_number in capsule.trace_rounds():
                try:
                    scenario = scenario_from_capsule(capsule, round_number=round_number)
                    result = engine.run(scenario).to_dict()
                    item = {
                        "round": round_number,
                        "ok": True,
                        "scenario": result["scenario"],
                        "signature": result["signature"],
                        "raw": result["raw"],
                    }
                except Exception as exc:
                    item = {"round": round_number, "ok": False, "error": str(exc)}
                replay_results.append(item)
                self._write_json(root / "replays" / f"round-{round_number:03d}.json", item)

        replay_successes = sum(1 for item in replay_results if item.get("ok"))
        manifest = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "tx_id": capsule.manifest.tx_id,
            "network": capsule.manifest.network,
            "capsule": {
                "path": capsule_path.name,
                "sha256": sha256_bytes(capsule_path.read_bytes()),
                "integrity_ok": bool(integrity.get("ok")),
            },
            "consensus": {
                "status": analysis.get("status") if isinstance(analysis, dict) else None,
                "execution_result": (
                    analysis.get("execution_result") if isinstance(analysis, dict) else None
                ),
                "successful": bool(analysis.get("successful")) if isinstance(analysis, dict) else False,
                "round_count": timeline.get("round_count"),
            },
            "capture": {
                "issue_count": len(issues) if isinstance(issues, list) else 0,
                "trace_rounds": capsule.trace_rounds(),
                "file_count": len(capsule.manifest.files),
            },
            "replay": {
                "attempted": len(replay_results),
                "successful": replay_successes,
                "failed": len(replay_results) - replay_successes,
            },
            "primary_cause": explanation.get("primary_cause"),
            "artifacts": [
                "incident.genreplay",
                "integrity.json",
                "timeline.json",
                "explanation.json",
                "analysis.json",
                "capture-issues.json",
                *[
                    f"replays/round-{item['round']:03d}.json"
                    for item in replay_results
                    if isinstance(item.get("round"), int)
                ],
            ],
        }
        self._write_json(root / "evidence.json", manifest)
        return manifest
