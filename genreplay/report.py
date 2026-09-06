from __future__ import annotations

from typing import Any

from .capsule import Capsule

REPORT_SCHEMA_VERSION = 1


def _norm(value: Any) -> str:
    return str(value or "").replace("_", "").replace("-", "").lower()


def _trace_details(capsule: Capsule, round_number: int) -> dict[str, Any]:
    path = f"traces/round-{round_number:03d}.json"
    if not capsule.has(path):
        return {
            "captured": False,
            "eq_output_count": 0,
            "result_code": None,
            "nondet_disagreement_call": None,
            "stderr_present": False,
        }
    trace = capsule.read_json(path)
    eq_outputs = trace.get("eq_outputs")
    if eq_outputs is None:
        eq_outputs = trace.get("eqOutputs")
    if not isinstance(eq_outputs, list):
        eq_outputs = []
    disagreement = trace.get("nondetDisagreementCallNo")
    if disagreement is None:
        disagreement = trace.get("nondet_disagreement_call_no")
    result_code = trace.get("result_code")
    if result_code is None:
        status = trace.get("status")
        if isinstance(status, dict):
            result_code = status.get("code")
    return {
        "captured": True,
        "eq_output_count": len(eq_outputs),
        "result_code": result_code,
        "nondet_disagreement_call": disagreement,
        "stderr_present": bool(trace.get("stderr")),
    }


def build_timeline(capsule: Capsule) -> dict[str, Any]:
    analysis = capsule.read_json("analysis/summary.json") if capsule.has("analysis/summary.json") else {}
    receipt = capsule.read_json("transaction/receipt.json")
    rounds: list[dict[str, Any]] = []
    raw_rounds = analysis.get("rounds") if isinstance(analysis, dict) else None
    if not isinstance(raw_rounds, list):
        raw_rounds = []

    for index, item in enumerate(raw_rounds):
        if not isinstance(item, dict):
            continue
        round_number = int(item.get("round", index))
        rounds.append(
            {
                "round": round_number,
                "leader_index": item.get("leader_index"),
                "leader": item.get("leader"),
                "committee_size": item.get("committee_size", 0),
                "votes_committed": item.get("votes_committed", 0),
                "votes_revealed": item.get("votes_revealed", 0),
                "rotations_left": item.get("rotations_left", 0),
                "appeal_bond": item.get("appeal_bond", "0"),
                "result": item.get("result"),
                "trace": _trace_details(capsule, round_number),
            }
        )

    transitions: list[dict[str, Any]] = []
    for previous, current in zip(rounds, rounds[1:], strict=False):
        changed: list[str] = []
        for key in (
            "leader",
            "committee_size",
            "votes_committed",
            "votes_revealed",
            "rotations_left",
            "appeal_bond",
            "result",
        ):
            if previous.get(key) != current.get(key):
                changed.append(key)
        if previous["trace"].get("eq_output_count") != current["trace"].get("eq_output_count"):
            changed.append("eq_output_count")
        if previous["trace"].get("nondet_disagreement_call") != current["trace"].get(
            "nondet_disagreement_call"
        ):
            changed.append("nondet_disagreement_call")
        transitions.append(
            {
                "from_round": previous["round"],
                "to_round": current["round"],
                "changed": changed,
            }
        )

    lifecycle = analysis.get("lifecycle") if isinstance(analysis, dict) else None
    message_count = len(receipt.get("messages") or []) if isinstance(receipt.get("messages"), list) else 0
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tx_id": capsule.manifest.tx_id,
        "network": capsule.manifest.network,
        "status": analysis.get("status") if isinstance(analysis, dict) else None,
        "execution_result": analysis.get("execution_result") if isinstance(analysis, dict) else None,
        "successful": bool(analysis.get("successful")) if isinstance(analysis, dict) else False,
        "round_count": len(rounds),
        "rounds": rounds,
        "transitions": transitions,
        "lifecycle": lifecycle,
        "emitted_message_count": message_count,
    }


def explain_capsule(capsule: Capsule) -> dict[str, Any]:
    timeline = build_timeline(capsule)
    analysis = capsule.read_json("analysis/summary.json") if capsule.has("analysis/summary.json") else {}
    warnings = analysis.get("warnings") if isinstance(analysis, dict) else []
    if not isinstance(warnings, list):
        warnings = []
    warning_codes = {
        str(item.get("code"))
        for item in warnings
        if isinstance(item, dict) and item.get("code") is not None
    }

    disagreement_rounds = [
        item["round"]
        for item in timeline["rounds"]
        if item["trace"].get("nondet_disagreement_call") is not None
    ]
    status_norm = _norm(timeline.get("status"))
    execution_norm = _norm(timeline.get("execution_result"))

    if disagreement_rounds:
        cause = "NONDETERMINISTIC_DISAGREEMENT"
        conclusion = (
            "GenVM trace evidence reports validator disagreement in nondeterministic equivalence "
            "evaluation. The listed round/call evidence is the strongest protocol-visible cause."
        )
    elif status_norm == "undetermined" or "UNDETERMINED" in warning_codes:
        cause = "CONSENSUS_UNDETERMINED"
        conclusion = (
            "The transaction did not obtain a consensus decision. No execution-success conclusion "
            "should be inferred from any leader output that was produced."
        )
    elif "timeout" in status_norm or "TIMEOUT" in warning_codes:
        cause = "CONSENSUS_TIMEOUT"
        conclusion = "The captured lifecycle contains a timeout outcome rather than ordinary completion."
    elif status_norm in {"accepted", "finalized"} and execution_norm not in {
        "finishedwithreturn",
        "success",
    }:
        cause = "EXECUTION_FAILED_AFTER_CONSENSUS"
        conclusion = (
            "Consensus reached a decided/finalized state, but the Intelligent Contract execution did "
            "not finish successfully. Finalized is therefore not equivalent to successful execution."
        )
    elif timeline.get("successful"):
        cause = "CONSENSUS_AND_EXECUTION_SUCCEEDED"
        conclusion = (
            "The captured transaction reached an accepted/finalized consensus state and the execution "
            "finished with a return value. No high-confidence failure cause is visible in the capsule."
        )
    else:
        cause = "CONSENSUS_STATE_REQUIRES_REVIEW"
        conclusion = "The captured evidence does not map to a stronger deterministic explanation rule."

    evidence: list[dict[str, Any]] = [
        {"kind": "status", "value": timeline.get("status")},
        {"kind": "execution_result", "value": timeline.get("execution_result")},
        {"kind": "round_count", "value": timeline.get("round_count")},
    ]
    for item in timeline["rounds"]:
        disagreement = item["trace"].get("nondet_disagreement_call")
        if disagreement is not None:
            evidence.append(
                {
                    "kind": "nondet_disagreement",
                    "round": item["round"],
                    "call": disagreement,
                }
            )
    if warning_codes:
        evidence.append({"kind": "warning_codes", "value": sorted(warning_codes)})

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tx_id": capsule.manifest.tx_id,
        "primary_cause": cause,
        "conclusion": conclusion,
        "evidence": evidence,
        "note": "This explanation is rule-based from captured protocol evidence; it does not call an AI model.",
    }
