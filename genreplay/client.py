from __future__ import annotations

from pathlib import Path
from typing import Any

from .capsule import Capsule
from .capture import CaptureService
from .doctor import run_doctor
from .evidence import EvidenceService
from .replay import ReplayEngine, scenario_from_capsule, scenario_from_receipt_outputs
from .report import build_timeline, explain_capsule
from .rpc import GenLayerRpcClient


class GenReplay:
    """Stable high-level Python API for GenReplay infrastructure workflows."""

    def __init__(self, rpc: str | GenLayerRpcClient | Any, *, timeout: float = 30.0):
        self.rpc = GenLayerRpcClient(rpc, timeout=timeout) if isinstance(rpc, str) else rpc

    def doctor(self, *, tx_id: str | None = None) -> dict[str, Any]:
        return run_doctor(self.rpc, tx_id=tx_id)

    def capture(self, tx_id: str, **kwargs: Any) -> Capsule:
        return CaptureService(self.rpc).capture(tx_id, **kwargs)

    def open(self, path: str | Path, *, verify: bool = True) -> Capsule:
        return Capsule.load(path, verify=verify)

    def timeline(self, capsule: Capsule | str | Path) -> dict[str, Any]:
        value = capsule if isinstance(capsule, Capsule) else self.open(capsule)
        return build_timeline(value)

    def explain(self, capsule: Capsule | str | Path) -> dict[str, Any]:
        value = capsule if isinstance(capsule, Capsule) else self.open(capsule)
        return explain_capsule(value)

    def replay(self, capsule: Capsule | str | Path, *, round_number: int = 0) -> dict[str, Any]:
        value = capsule if isinstance(capsule, Capsule) else self.open(capsule)
        scenario = scenario_from_capsule(value, round_number=round_number)
        return ReplayEngine(self.rpc).run(scenario).to_dict()

    def replay_receipt(self, capsule: Capsule | str | Path) -> dict[str, Any]:
        """Replay transaction-level receipt eqBlocksOutputs without round attribution."""
        value = capsule if isinstance(capsule, Capsule) else self.open(capsule)
        scenario = scenario_from_receipt_outputs(value)
        return ReplayEngine(self.rpc).run(scenario).to_dict()

    def replay_all(self, capsule: Capsule | str | Path) -> list[dict[str, Any]]:
        value = capsule if isinstance(capsule, Capsule) else self.open(capsule)
        results: list[dict[str, Any]] = []
        for round_number in value.trace_rounds():
            try:
                results.append(
                    {
                        "source": "round-trace",
                        "round": round_number,
                        "round_attributed": True,
                        "ok": True,
                        "result": self.replay(value, round_number=round_number),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "source": "round-trace",
                        "round": round_number,
                        "round_attributed": True,
                        "ok": False,
                        "error": str(exc),
                    }
                )
        try:
            results.append(
                {
                    "source": "receipt.eqBlocksOutputs",
                    "round": None,
                    "round_attributed": False,
                    "ok": True,
                    "result": self.replay_receipt(value),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "source": "receipt.eqBlocksOutputs",
                    "round": None,
                    "round_attributed": False,
                    "ok": False,
                    "error": str(exc),
                }
            )
        return results

    def evidence(self, tx_id: str, output_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
        return EvidenceService(self.rpc).generate(tx_id, output_dir, **kwargs)
