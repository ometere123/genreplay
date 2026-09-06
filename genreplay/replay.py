from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from .capsule import Capsule
from .errors import ReplayError
from .models import ReplayResult, ReplayScenario
from .util import ensure_hex_prefix, hex_quantity


class ReplayRpc(Protocol):
    endpoint: str

    def gen_call(self, request: dict[str, Any]) -> dict[str, Any]: ...


def _trace_eq_outputs(trace: dict[str, Any]) -> list[str]:
    raw = trace.get("eq_outputs")
    if raw is None:
        raw = trace.get("eqOutputs")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReplayError("captured trace eq_outputs is not an array")
    return [ensure_hex_prefix(str(item)) for item in raw]


def scenario_from_capsule(capsule: Capsule, *, round_number: int = 0) -> ReplayScenario:
    receipt = capsule.read_json("transaction/receipt.json")
    trace_name = f"traces/round-{round_number:03d}.json"
    if not capsule.has(trace_name):
        available = ", ".join(str(v) for v in capsule.trace_rounds()) or "none"
        raise ReplayError(f"capsule has no trace for round {round_number}; available rounds: {available}")
    trace = capsule.read_json(trace_name)
    leader_results = _trace_eq_outputs(trace)
    if not leader_results:
        raise ReplayError(
            "captured trace has no equivalence outputs; validator-mode replay requires leader_results"
        )

    sender = receipt.get("sender") or receipt.get("txOrigin")
    recipient = receipt.get("recipient")
    data = receipt.get("txCallData")
    if not isinstance(sender, str) or not isinstance(recipient, str) or not isinstance(data, str):
        raise ReplayError("receipt does not contain sender, recipient, and txCallData")

    block_number = capsule.manifest.network.get("historical_state_block")
    if block_number is None:
        ranges = receipt.get("readStateBlockRanges") or []
        if ranges and isinstance(ranges[0], dict):
            block = ranges[0].get("ProcessingBlock") or ranges[0].get("ProposalBlock")
            if block:
                block_number = hex_quantity(block)

    value = None
    fees = receipt.get("fees")
    if isinstance(fees, dict) and fees.get("userValue") is not None:
        try:
            value = hex_quantity(fees["userValue"])
        except Exception:
            value = None

    return ReplayScenario(
        version=1,
        source_tx_id=capsule.manifest.tx_id,
        rpc_hint=capsule.manifest.network.get("rpc_url"),
        from_address=sender,
        to_address=recipient,
        call_type="write",
        data=ensure_hex_prefix(data),
        status="accepted",
        block_number=block_number,
        value=value,
        leader_results=leader_results,
        round_number=round_number,
        notes=[
            "Validator-mode replay uses captured leader equivalence outputs.",
            "Validator-side nondeterminism is evaluated by the target RPC at replay time.",
        ],
    )


def replay_signature(raw: dict[str, Any]) -> dict[str, Any]:
    status = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    disagreement = raw.get("nondetDisagreementCallNo")
    if disagreement is None:
        disagreement = raw.get("nondet_disagreement_call_no")
    return {
        "status_code": status.get("code"),
        "status_message": status.get("message"),
        "nondet_disagreement_call": disagreement,
        "return_data": raw.get("data") or raw.get("return_data"),
        "stderr_present": bool(raw.get("stderr")),
        "event_count": len(raw.get("events") or []) if isinstance(raw.get("events"), list) else 0,
        "message_count": len(raw.get("messages") or []) if isinstance(raw.get("messages"), list) else 0,
    }


class ReplayEngine:
    def __init__(self, rpc: ReplayRpc):
        self.rpc = rpc

    def run(self, scenario: ReplayScenario) -> ReplayResult:
        if not scenario.leader_results:
            raise ReplayError("scenario has no leader_results; refusing to pretend this is validator replay")
        raw = self.rpc.gen_call(scenario.to_gen_call_request())
        return ReplayResult(
            scenario=scenario.to_dict(),
            raw=raw,
            signature=replay_signature(raw),
        )

    def minimize_leader_prefix(
        self,
        scenario: ReplayScenario,
        *,
        target_signature: dict[str, Any] | None = None,
    ) -> tuple[ReplayScenario, list[dict[str, Any]]]:
        """Find the shortest leader-results prefix preserving the observed replay signature.

        This is deliberately conservative: equivalence outputs are opaque GenVM bytes, so GenReplay
        never mutates their internals. It only tests shorter ordered prefixes and keeps a reduction
        when the live validator replay produces the exact same diagnostic signature.
        """
        baseline_result = self.run(scenario)
        target = target_signature or baseline_result.signature
        trials: list[dict[str, Any]] = [
            {
                "prefix_length": len(scenario.leader_results),
                "signature": baseline_result.signature,
                "kept": True,
            }
        ]
        best = scenario
        for length in range(len(scenario.leader_results) - 1, 0, -1):
            candidate = replace(
                scenario,
                leader_results=list(scenario.leader_results[:length]),
                notes=list(scenario.notes) + [f"Reduced leader_results prefix to {length} entries."],
            )
            try:
                result = self.run(candidate)
                kept = result.signature == target
                trials.append({"prefix_length": length, "signature": result.signature, "kept": kept})
                if kept:
                    best = candidate
            except Exception as exc:
                trials.append({"prefix_length": length, "error": str(exc), "kept": False})
        return best, trials
