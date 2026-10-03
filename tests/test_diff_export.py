import json
from pathlib import Path

import pytest

from genreplay.capsule import Capsule
from genreplay.diffing import diff_capsules, json_diff
from genreplay.errors import ReplayError
from genreplay.export import export_pytest, normalise_regression_signature
from genreplay.replay import ReplayEngine, scenario_from_receipt_outputs
from genreplay.util import canonical_json_bytes, sha256_bytes

from .helpers import TX_ID


def cap(status: str) -> Capsule:
    return Capsule.build(
        tool_version="0.1.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"chain_id": 61999},
        files={
            "transaction/receipt.json": b"{}\n",
            "analysis/summary.json": canonical_json_bytes({"status": status}),
            "capture/issues.json": b"[]\n",
        },
    )


def test_json_diff_reports_nested_change():
    changes = json_diff({"a": {"b": 1}}, {"a": {"b": 2}})
    assert changes == [{"path": "$.a.b", "kind": "changed", "before": 1, "after": 2}]


def test_capsule_diff_compares_analysis():
    result = diff_capsules(cap("Accepted"), cap("Finalized"))
    assert any(item["path"] == "$.status" for item in result["analysis"])


def test_exported_test_contains_identity(tmp_path: Path):
    capsule_path = tmp_path / "incident.genreplay"
    cap("Finalized").write(capsule_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({
        "source": "round-trace",
        "scenario": {
            "version": 1, "source_tx_id": TX_ID, "rpc_hint": "http://localhost:4000/api",
            "from_address": "0x" + "aa" * 20, "to_address": "0x" + "bb" * 20,
            "call_type": "write", "data": "0xdeadbeef", "status": "accepted",
            "block_number": "0x65", "leader_results": ["0x01"], "round_number": 0,
        },
        "signature": {"status_code": 0, "nondet_disagreement_call": 1, "return_data": "0x00", "stderr_present": False, "event_count": 0, "message_count": 0},
    }))
    output = export_pytest(capsule_path, tmp_path / "test_incident.py", baseline=baseline)
    text = output.read_text()
    assert TX_ID in text
    assert "GENREPLAY_RPC" in text
    assert "verify_integrity" in text
    assert (tmp_path / "replays" / f"{TX_ID[2:10]}.genreplay").exists()
    assert "Path(__file__).parent" in text
    assert "return_data_sha256" in text


def test_export_refuses_capsule_without_behavioural_baseline(tmp_path: Path):
    capsule_path = tmp_path / "incident.genreplay"
    cap("Finalized").write(capsule_path)
    with pytest.raises(ReplayError, match="baseline"):
        export_pytest(capsule_path, tmp_path / "test_incident.py")


def test_transaction_level_export_preserves_null_round(tmp_path: Path):
    from .test_replay import FakeReplayRpc, make_receipt_fallback_capsule

    capsule = make_receipt_fallback_capsule("c9010286706164646564", rounds=2)
    capsule_path = tmp_path / "incident.genreplay"
    capsule.write(capsule_path)
    result = ReplayEngine(FakeReplayRpc()).run(scenario_from_receipt_outputs(capsule)).to_dict()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"source": "receipt.eqBlocksOutputs", **result}))
    output = export_pytest(capsule_path, tmp_path / "test_incident.py", baseline=baseline)
    text = output.read_text(encoding="utf-8")
    assert "'source_mode': 'receipt.eqBlocksOutputs'" in text
    assert "'round_number': None" in text
    assert "scenario_from_receipt_outputs" in text


@pytest.mark.parametrize("field, changed", [
    ("status_code", 1), ("nondet_disagreement_call", 9),
    ("return_data_sha256", sha256_bytes(b"0x99")), ("event_count", 2), ("message_count", 3),
])
def test_stable_signature_detects_drift(field: str, changed: object):
    before = normalise_regression_signature({"status_code": 0, "nondet_disagreement_call": 1, "return_data": "0x00", "stderr_present": False, "event_count": 0, "message_count": 0})
    after = dict(before)
    after[field] = changed
    assert after != before


def test_masked_signature_field_does_not_fail_comparison():
    expected = normalise_regression_signature({"status_code": 0, "return_data": "0x00"})
    actual = dict(expected)
    actual["event_count"] = 99
    fields = ["status_code", "return_data_sha256"]
    assert {key: actual[key] for key in fields} == {key: expected[key] for key in fields}
