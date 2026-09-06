from __future__ import annotations

from typing import Any

from .rpc import GenLayerRpcClient


def run_doctor(rpc: GenLayerRpcClient) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    try:
        chain_id = rpc.chain_id()
        checks.append({"name": "eth_chainId", "ok": True, "value": chain_id})
    except Exception as exc:
        chain_id = None
        checks.append({"name": "eth_chainId", "ok": False, "error": str(exc)})

    try:
        pong = rpc.ping()
        checks.append({"name": "gen_dbg_ping", "ok": True, "value": pong})
    except Exception as exc:
        checks.append({"name": "gen_dbg_ping", "ok": False, "error": str(exc)})

    # Method presence cannot be probed safely without a valid tx/address. The doctor therefore
    # reports the two zero-side-effect calls it can prove and lists the capture surfaces GenReplay
    # will exercise when a transaction is supplied.
    required_on_capture = [
        "gen_getTransactionReceipt",
        "gen_getTransactionLifecycle",
        "gen_dbg_traceTransaction",
        "gen_getContractCode",
        "gen_getContractSchema",
        "gen_getContractState",
        "gen_call",
    ]
    return {
        "endpoint": rpc.endpoint,
        "chain_id": chain_id,
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "capture_surfaces": required_on_capture,
    }
