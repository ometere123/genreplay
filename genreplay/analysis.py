from __future__ import annotations

from typing import Any

from .util import parse_int


def _norm(value: Any) -> str:
    return str(value or "").replace("_", "").replace("-", "").lower()


def execution_succeeded(receipt: dict[str, Any]) -> bool:
    status = _norm(receipt.get("statusName"))
    execution = _norm(receipt.get("txExecutionResultName"))
    return status in {"accepted", "finalized"} and execution in {
        "finishedwithreturn",
        "success",
    }


def analyze_receipt(
    receipt: dict[str, Any],
    *,
    lifecycle: dict[str, Any] | None = None,
    traces: dict[int, dict[str, Any]] | None = None,
    contract_code_captured: bool = False,
) -> dict[str, Any]:
    traces = traces or {}
    status_name = str(receipt.get("statusName") or receipt.get("status") or "UNKNOWN")
    execution_name = str(
        receipt.get("txExecutionResultName") or receipt.get("txExecutionResult") or "UNKNOWN"
    )
    rounds: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    round_data = receipt.get("roundData") or []
    if not isinstance(round_data, list):
        round_data = []

    for index, item in enumerate(round_data):
        if not isinstance(item, dict):
            continue
        validators = item.get("roundValidators") or []
        if not isinstance(validators, list):
            validators = []
        leader_index = parse_int(item.get("leaderIndex"), -1)
        leader = validators[leader_index] if 0 <= leader_index < len(validators) else None
        trace = traces.get(index) or traces.get(parse_int(item.get("round"), index))
        disagreement = None
        if trace:
            disagreement = trace.get("nondetDisagreementCallNo")
            if disagreement is None:
                disagreement = trace.get("nondet_disagreement_call_no")
        rounds.append(
            {
                "round": parse_int(item.get("round"), index),
                "leader_index": leader_index,
                "leader": leader,
                "committee_size": len(validators),
                "validators": validators,
                "votes_committed": parse_int(item.get("votesCommitted")),
                "votes_revealed": parse_int(item.get("votesRevealed")),
                "rotations_left": parse_int(item.get("rotationsLeft")),
                "appeal_bond": str(item.get("appealBond", "0")),
                "result": item.get("result"),
                "trace_captured": trace is not None,
                "nondet_disagreement_call": disagreement,
            }
        )

        if validators and parse_int(item.get("votesRevealed")) < len(validators):
            warnings.append(
                {
                    "code": "PARTIAL_REVEAL",
                    "severity": "info",
                    "round": index,
                    "message": "fewer votes are revealed than committee members in the captured receipt",
                }
            )
        if disagreement is not None:
            warnings.append(
                {
                    "code": "TRACE_NONDET_DISAGREEMENT",
                    "severity": "high",
                    "round": index,
                    "message": f"trace reports nondeterministic disagreement at call {disagreement}",
                }
            )

    status_norm = _norm(status_name)
    execution_norm = _norm(execution_name)
    if status_norm in {"accepted", "finalized"} and execution_norm not in {
        "finishedwithreturn",
        "success",
    }:
        warnings.append(
            {
                "code": "DECIDED_BUT_EXECUTION_NOT_SUCCESSFUL",
                "severity": "high",
                "message": "consensus status is decided/finalized but execution did not finish with return",
            }
        )
    if status_norm == "undetermined":
        warnings.append(
            {
                "code": "UNDETERMINED",
                "severity": "high",
                "message": "the transaction did not reach a consensus result",
            }
        )
    if "timeout" in status_norm or "timeout" in execution_norm:
        warnings.append(
            {
                "code": "TIMEOUT",
                "severity": "high",
                "message": "the captured transaction contains a timeout outcome",
            }
        )

    if lifecycle:
        action = str(lifecycle.get("resolutionAction") or "")
        if _norm(action) == "finalize" and status_norm != "finalized":
            warnings.append(
                {
                    "code": "FINALIZATION_ACTION_AVAILABLE",
                    "severity": "info",
                    "message": (
                        "lifecycle projection says Finalize is available while stored status "
                        "is not Finalized"
                    ),
                }
            )
        if action and _norm(action) not in {"noop", "unspecified"}:
            if lifecycle.get("decisionId") is None or lifecycle.get("decisionActive") is False:
                warnings.append(
                    {
                        "code": "INACTIVE_DECISION_FOR_ACTION",
                        "severity": "medium",
                        "message": "a lifecycle action is reported without an active decision identity",
                    }
                )

    if not contract_code_captured:
        warnings.append(
            {
                "code": "CONTRACT_CODE_NOT_CAPTURED",
                "severity": "medium",
                "message": "historical contract source was unavailable; source-level replay is incomplete",
            }
        )

    return {
        "tx_id": receipt.get("id"),
        "status": status_name,
        "execution_result": execution_name,
        "successful": execution_succeeded(receipt),
        "recipient": receipt.get("recipient"),
        "sender": receipt.get("sender"),
        "tx_origin": receipt.get("txOrigin"),
        "epoch": receipt.get("epoch"),
        "random_seed": receipt.get("randomSeed"),
        "initial_validator_count": parse_int(receipt.get("numOfInitialValidators")),
        "initial_rotations": parse_int(receipt.get("initialRotations")),
        "round_count": len(rounds),
        "rounds": rounds,
        "lifecycle": lifecycle,
        "warnings": warnings,
    }
