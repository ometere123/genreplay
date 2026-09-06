from genreplay.analysis import analyze_receipt, execution_succeeded

from .helpers import lifecycle, receipt, trace


def test_success_requires_status_and_execution():
    assert execution_succeeded(receipt()) is True
    assert execution_succeeded(receipt(execution="FinishedWithError")) is False
    assert execution_succeeded(receipt(status="Undetermined")) is False


def test_round_leader_is_resolved():
    result = analyze_receipt(
        receipt(), lifecycle=lifecycle(), traces={0: trace()}, contract_code_captured=True
    )
    assert result["rounds"][0]["leader"] == result["rounds"][0]["validators"][1]


def test_finalized_error_warns():
    result = analyze_receipt(receipt(execution="FinishedWithError"), contract_code_captured=True)
    codes = {item["code"] for item in result["warnings"]}
    assert "DECIDED_BUT_EXECUTION_NOT_SUCCESSFUL" in codes


def test_undetermined_warns():
    result = analyze_receipt(receipt(status="Undetermined"), contract_code_captured=True)
    assert "UNDETERMINED" in {item["code"] for item in result["warnings"]}


def test_trace_disagreement_warns():
    result = analyze_receipt(receipt(), traces={0: trace(disagreement=1)}, contract_code_captured=True)
    warning = next(item for item in result["warnings"] if item["code"] == "TRACE_NONDET_DISAGREEMENT")
    assert warning["round"] == 0


def test_missing_contract_code_warns():
    result = analyze_receipt(receipt(), contract_code_captured=False)
    assert "CONTRACT_CODE_NOT_CAPTURED" in {item["code"] for item in result["warnings"]}


def test_finalize_action_warns_before_finalized():
    r = receipt(status="Accepted")
    lc = lifecycle(action="Finalize")
    lc["storedStatus"] = "Accepted"
    result = analyze_receipt(r, lifecycle=lc, contract_code_captured=True)
    assert "FINALIZATION_ACTION_AVAILABLE" in {item["code"] for item in result["warnings"]}
