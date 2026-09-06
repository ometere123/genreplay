from __future__ import annotations

from typing import Any

TRANSACTION_STATUS_NAMES = {
    0: "UNINITIALIZED",
    1: "PENDING",
    2: "PROPOSING",
    3: "COMMITTING",
    4: "REVEALING",
    5: "ACCEPTED",
    6: "UNDETERMINED",
    7: "FINALIZED",
    8: "CANCELED",
    9: "APPEAL_REVEALING",
    10: "APPEAL_COMMITTING",
    11: "READY_TO_FINALIZE",
    12: "VALIDATORS_TIMEOUT",
    13: "LEADER_TIMEOUT",
    14: "LEADER_REVEALING",
}

EXECUTION_RESULT_NAMES = {
    0: "NOT_VOTED",
    1: "FINISHED_WITH_RETURN",
    2: "FINISHED_WITH_ERROR",
    3: "TIMEOUT",
    4: "NONDET_DISAGREE",
    5: "DETERMINISTIC_VIOLATION",
}

ROUND_RESULT_NAMES = {
    0: "IDLE",
    1: "MAJORITY_AGREE",
    2: "MAJORITY_DISAGREE",
    3: "MAJORITY_TIMEOUT",
    4: "DETERMINISTIC_VIOLATION",
    5: "NO_MAJORITY",
}


def _int_like(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        try:
            return int(raw, 16) if raw.lower().startswith("0x") else int(raw)
        except ValueError:
            return None
    return None


def transaction_status_name(receipt: dict[str, Any]) -> str:
    explicit = receipt.get("statusName")
    if isinstance(explicit, str) and explicit.strip():
        return explicit
    code = _int_like(receipt.get("status"))
    return TRANSACTION_STATUS_NAMES.get(code, str(receipt.get("status") or "UNKNOWN"))


def execution_result_name(receipt: dict[str, Any]) -> str:
    explicit = receipt.get("txExecutionResultName")
    if isinstance(explicit, str) and explicit.strip():
        return explicit
    code = _int_like(receipt.get("txExecutionResult"))
    return EXECUTION_RESULT_NAMES.get(code, str(receipt.get("txExecutionResult") or "UNKNOWN"))


def round_result_name(value: Any) -> str:
    code = _int_like(value)
    return ROUND_RESULT_NAMES.get(code, str(value if value is not None else "UNKNOWN"))
