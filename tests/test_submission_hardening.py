from pathlib import Path

from genreplay.capture import CaptureService
from genreplay.doctor import run_doctor
from genreplay.evidence import EvidenceService, verify_evidence_bundle
from genreplay.report import build_timeline, explain_capsule

from .helpers import TX_ID, receipt, trace
from .test_capture import FakeCaptureRpc


class FullReplayRpc(FakeCaptureRpc):
    def ping(self):
        return "pong"

    def gen_call(self, request):
        assert request["leader_results"]
        return {
            "status": {"code": 0, "message": "success"},
            "data": "0x00",
            "stderr": "",
            "events": [],
            "messages": [],
        }


class DisagreementRpc(FullReplayRpc):
    def debug_trace_transaction(self, tx_id, *, round_number=0):
        return trace(disagreement=2, eq_outputs=[f"0x0{round_number + 1}"])


class ReceiptOnlyReplayRpc(FullReplayRpc):
    def get_transaction_receipt(self, tx_id):
        value = receipt(rounds=2)
        value["eqBlocksOutputs"] = "c9010286706164646564"
        return value

    def debug_trace_transaction(self, tx_id, *, round_number=0):
        return trace(eq_outputs=[])


class NotVotedRpc(FullReplayRpc):
    def get_transaction_receipt(self, tx_id):
        value = receipt(rounds=1, execution="NOT_VOTED")
        value["txExecutionResult"] = 0
        return value


def test_timeline_tracks_multiple_rounds():
    capsule = CaptureService(FullReplayRpc()).capture(TX_ID)
    timeline = build_timeline(capsule)
    assert timeline["schema_version"] == 1
    assert timeline["round_count"] == 2
    assert timeline["rounds"][0]["trace"]["eq_output_count"] == 1
    assert timeline["transitions"][0]["from_round"] == 0
    assert timeline["transitions"][0]["to_round"] == 1


def test_explain_is_rule_based_and_finds_disagreement():
    capsule = CaptureService(DisagreementRpc()).capture(TX_ID)
    result = explain_capsule(capsule)
    assert result["primary_cause"] == "NONDETERMINISTIC_DISAGREEMENT"
    assert any(item["kind"] == "nondet_disagreement" for item in result["evidence"])
    assert "does not call an AI model" in result["note"]


def test_not_voted_is_not_mislabeled_as_runtime_failure():
    capsule = CaptureService(NotVotedRpc()).capture(TX_ID)
    analysis = capsule.read_json("analysis/summary.json")
    codes = {item["code"] for item in analysis["warnings"]}
    assert "DECIDED_WITHOUT_EXECUTION_VOTE" in codes
    assert "DECIDED_BUT_EXECUTION_NOT_SUCCESSFUL" not in codes
    explanation = explain_capsule(capsule)
    assert explanation["primary_cause"] == "EXECUTION_RESULT_NOT_VOTED"
    assert "not as proof of a contract runtime error" in explanation["conclusion"]


def test_deep_doctor_proves_round_validator_replay():
    result = run_doctor(FullReplayRpc(), tx_id=TX_ID)
    assert result["ok"] is True
    assert result["grade"] == "FULL"
    assert result["capabilities"]["validator_replay"] == "available"
    assert result["capabilities"]["validator_replay_source"] == "round-trace"
    assert result["capabilities"]["validator_replay_round_attributed"] is True
    assert result["transaction"]["integrity"]["ok"] is True


def test_deep_doctor_falls_back_to_transaction_level_receipt_replay():
    result = run_doctor(ReceiptOnlyReplayRpc(), tx_id=TX_ID)
    assert result["grade"] == "FULL"
    assert result["capabilities"]["validator_replay"] == "available"
    assert result["capabilities"]["validator_replay_source"] == "receipt.eqBlocksOutputs"
    assert result["capabilities"]["validator_replay_round_attributed"] is False


def test_evidence_bundle_contains_reviewer_artifacts(tmp_path: Path):
    output = tmp_path / "evidence"
    result = EvidenceService(FullReplayRpc()).generate(TX_ID, output)
    assert result["capsule"]["integrity_ok"] is True
    assert result["replay"]["attempted"] == 3
    assert result["replay"]["successful"] == 2
    assert result["replay"]["successful_sources"] == ["round-trace", "round-trace"]
    assert "timeline.json" in result["artifact_integrity"]
    assert (output / "incident.genreplay").exists()
    assert (output / "evidence.json").exists()
    assert (output / "timeline.json").exists()
    assert (output / "explanation.json").exists()
    assert (output / "replays" / "round-000.json").exists()
    assert (output / "replays" / "round-001.json").exists()
    assert (output / "replays" / "receipt-current.json").exists()
    verified = verify_evidence_bundle(output)
    assert verified["ok"] is True
    assert verified["file_count"] == len(result["artifacts"])


def test_evidence_bundle_tampering_is_detected(tmp_path: Path):
    output = tmp_path / "evidence"
    EvidenceService(FullReplayRpc()).generate(TX_ID, output)
    (output / "timeline.json").write_text("{}\n", encoding="utf-8")
    verified = verify_evidence_bundle(output)
    assert verified["ok"] is False
    assert "digest mismatch: timeline.json" in verified["errors"]


def test_evidence_bundle_records_successful_transaction_level_replay(tmp_path: Path):
    output = tmp_path / "receipt-evidence"
    result = EvidenceService(ReceiptOnlyReplayRpc()).generate(TX_ID, output)
    assert result["replay"]["successful"] == 1
    assert result["replay"]["successful_sources"] == ["receipt.eqBlocksOutputs"]
    stored = (output / "replays" / "receipt-current.json").read_text(encoding="utf-8")
    assert '"round_attributed": false' in stored
