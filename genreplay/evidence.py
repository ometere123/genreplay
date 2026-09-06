from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .capsule import Capsule
from .capture import CaptureService
from .replay import ReplayEngine, scenario_from_capsule, scenario_from_receipt_outputs
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

    @staticmethod
    def _artifact_metadata(root: Path, artifacts: list[str]) -> dict[str, dict[str, Any]]:
        metadata: dict[str, dict[str, Any]] = {}
        for relative in artifacts:
            path = root / relative
            data = path.read_bytes()
            metadata[relative] = {"sha256": sha256_bytes(data), "size": len(data)}
        return metadata

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
        replay_artifacts: list[str] = []
        if replay_rounds:
            engine = ReplayEngine(self.rpc)
            for round_number in capsule.trace_rounds():
                path = f"replays/round-{round_number:03d}.json"
                try:
                    scenario = scenario_from_capsule(capsule, round_number=round_number)
                    result = engine.run(scenario).to_dict()
                    item = {
                        "source": "round-trace",
                        "round": round_number,
                        "round_attributed": True,
                        "ok": True,
                        "scenario": result["scenario"],
                        "signature": result["signature"],
                        "raw": result["raw"],
                    }
                except Exception as exc:
                    item = {
                        "source": "round-trace",
                        "round": round_number,
                        "round_attributed": True,
                        "ok": False,
                        "error": str(exc),
                    }
                replay_results.append(item)
                replay_artifacts.append(path)
                self._write_json(root / path, item)

            receipt_path = "replays/receipt-current.json"
            try:
                scenario = scenario_from_receipt_outputs(capsule)
                result = engine.run(scenario).to_dict()
                item = {
                    "source": "receipt.eqBlocksOutputs",
                    "round": None,
                    "round_attributed": False,
                    "ok": True,
                    "scenario": result["scenario"],
                    "signature": result["signature"],
                    "raw": result["raw"],
                }
            except Exception as exc:
                item = {
                    "source": "receipt.eqBlocksOutputs",
                    "round": None,
                    "round_attributed": False,
                    "ok": False,
                    "error": str(exc),
                }
            replay_results.append(item)
            replay_artifacts.append(receipt_path)
            self._write_json(root / receipt_path, item)

        replay_successes = sum(1 for item in replay_results if item.get("ok"))
        successful_sources = [str(item.get("source")) for item in replay_results if item.get("ok")]
        artifacts = [
            "incident.genreplay",
            "integrity.json",
            "timeline.json",
            "explanation.json",
            "analysis.json",
            "capture-issues.json",
            *replay_artifacts,
        ]
        artifact_integrity = self._artifact_metadata(root, artifacts)
        manifest = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "tx_id": capsule.manifest.tx_id,
            "network": capsule.manifest.network,
            "capsule": {
                "path": capsule_path.name,
                "sha256": artifact_integrity["incident.genreplay"]["sha256"],
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
                "successful_sources": successful_sources,
            },
            "primary_cause": explanation.get("primary_cause"),
            "artifacts": artifacts,
            "artifact_integrity": artifact_integrity,
        }
        self._write_json(root / "evidence.json", manifest)
        return manifest


def verify_evidence_bundle(output_dir: str | Path) -> dict[str, Any]:
    """Verify a generated evidence bundle without contacting a GenLayer network."""

    root = Path(output_dir)
    manifest_path = root / "evidence.json"
    errors: list[str] = []
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "ok": False,
            "errors": [f"invalid evidence.json: {exc}"],
            "file_count": 0,
        }
    if not isinstance(manifest_raw, dict):
        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "ok": False,
            "errors": ["evidence.json must contain an object"],
            "file_count": 0,
        }
    if manifest_raw.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"unsupported evidence schema version: {manifest_raw.get('schema_version')!r}"
        )

    integrity = manifest_raw.get("artifact_integrity")
    if not isinstance(integrity, dict):
        errors.append("evidence bundle has no artifact_integrity manifest")
        integrity = {}

    for relative, metadata in integrity.items():
        if not isinstance(relative, str) or not isinstance(metadata, dict):
            errors.append(f"invalid artifact metadata: {relative!r}")
            continue
        path = root / relative
        try:
            resolved = path.resolve()
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            errors.append(f"unsafe artifact path: {relative}")
            continue
        if not path.is_file():
            errors.append(f"missing artifact: {relative}")
            continue
        data = path.read_bytes()
        if sha256_bytes(data) != str(metadata.get("sha256")):
            errors.append(f"digest mismatch: {relative}")
        try:
            expected_size = int(metadata.get("size", -1))
        except (TypeError, ValueError):
            expected_size = -1
        if len(data) != expected_size:
            errors.append(f"size mismatch: {relative}")

    capsule_path = root / "incident.genreplay"
    if capsule_path.is_file():
        try:
            Capsule.load(capsule_path, verify=True)
        except Exception as exc:
            errors.append(f"capsule verification failed: {exc}")
    else:
        errors.append("missing artifact: incident.genreplay")

    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "ok": not errors,
        "errors": errors,
        "file_count": len(integrity),
        "tx_id": manifest_raw.get("tx_id"),
    }
