from __future__ import annotations

from typing import Any

from .capture import CaptureService
from .replay import ReplayEngine, scenario_from_capsule
from .rpc import GenLayerRpcClient


def _check(name: str, fn: Any) -> dict[str, Any]:
    try:
        value = fn()
        return {"name": name, "ok": True, "value": value}
    except Exception as exc:
        return {"name": name, "ok": False, "error": str(exc)}


def run_doctor(rpc: GenLayerRpcClient, *, tx_id: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    chain_check = _check("eth_chainId", rpc.chain_id)
    checks.append(chain_check)
    chain_id = chain_check.get("value") if chain_check["ok"] else None
    checks.append(_check("gen_dbg_ping", rpc.ping))

    required_on_capture = [
        "gen_getTransactionReceipt",
        "gen_getTransactionLifecycle",
        "gen_dbg_traceTransaction",
        "gen_getContractCode",
        "gen_getContractSchema",
        "gen_getContractState",
        "gen_call",
    ]

    capabilities: dict[str, Any] = {
        "mode": "connectivity" if tx_id is None else "transaction",
        "capture": "unproven",
        "validator_replay": "unproven",
        "historical_source": "unproven",
        "historical_state": "unproven",
        "lifecycle": "unproven",
        "debug_trace": "unproven",
    }
    transaction: dict[str, Any] | None = None

    if tx_id is not None:
        try:
            capsule = CaptureService(rpc).capture(tx_id)
            issues = capsule.read_json("capture/issues.json")
            issue_stages = {
                str(item.get("stage"))
                for item in issues
                if isinstance(item, dict) and item.get("stage") is not None
            }
            capabilities.update(
                {
                    "capture": "full" if not issues else "partial",
                    "historical_source": (
                        "available" if capsule.has("contract/source.b64") else "unavailable"
                    ),
                    "historical_state": (
                        "available" if capsule.has("contract/state.hex") else "unavailable"
                    ),
                    "lifecycle": (
                        "available" if capsule.has("transaction/lifecycle.json") else "unavailable"
                    ),
                    "debug_trace": "available" if capsule.trace_rounds() else "unavailable",
                    "capture_issue_stages": sorted(issue_stages),
                }
            )
            transaction = {
                "tx_id": capsule.manifest.tx_id,
                "trace_rounds": capsule.trace_rounds(),
                "file_count": len(capsule.manifest.files),
                "integrity": capsule.verify_integrity(),
                "analysis": capsule.read_json("analysis/summary.json"),
            }
            checks.append(
                {
                    "name": "transaction_capture",
                    "ok": True,
                    "value": {
                        "files": len(capsule.manifest.files),
                        "issues": len(issues) if isinstance(issues, list) else 0,
                    },
                }
            )

            if capsule.trace_rounds():
                round_number = capsule.trace_rounds()[0]
                try:
                    scenario = scenario_from_capsule(capsule, round_number=round_number)
                    replay = ReplayEngine(rpc).run(scenario)
                    capabilities["validator_replay"] = "available"
                    checks.append(
                        {
                            "name": "validator_mode_gen_call",
                            "ok": True,
                            "value": replay.signature,
                        }
                    )
                except Exception as exc:
                    capabilities["validator_replay"] = "failed"
                    checks.append(
                        {
                            "name": "validator_mode_gen_call",
                            "ok": False,
                            "error": str(exc),
                        }
                    )
            else:
                capabilities["validator_replay"] = "unavailable"
                checks.append(
                    {
                        "name": "validator_mode_gen_call",
                        "ok": False,
                        "error": "no captured trace round exposes leader equivalence outputs",
                    }
                )
        except Exception as exc:
            capabilities["capture"] = "failed"
            checks.append({"name": "transaction_capture", "ok": False, "error": str(exc)})

    core_ok = all(check["ok"] for check in checks[:2])
    if tx_id is None:
        grade = "CONNECTIVITY_ONLY" if core_ok else "UNAVAILABLE"
    elif not core_ok or capabilities["capture"] == "failed":
        grade = "UNAVAILABLE"
    elif capabilities["validator_replay"] == "available" and capabilities["capture"] == "full":
        grade = "FULL"
    elif capabilities["validator_replay"] == "available":
        grade = "REPLAY_READY_PARTIAL_CAPTURE"
    else:
        grade = "CAPTURE_ONLY"

    return {
        "schema_version": 1,
        "endpoint": rpc.endpoint,
        "chain_id": chain_id,
        "ok": core_ok and (tx_id is None or capabilities["capture"] != "failed"),
        "grade": grade,
        "checks": checks,
        "capabilities": capabilities,
        "transaction": transaction,
        "capture_surfaces": required_on_capture,
    }
