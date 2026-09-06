from pathlib import Path

from genreplay.capture import CaptureService
from genreplay.doctor import run_doctor
from genreplay.evidence import EvidenceService
from genreplay.report import build_timeline, explain_capsule

from .helpers import TX_ID, trace
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


def test_deep_doctor_proves_capture_and_validator_replay():
    result = run_doctor(FullReplayRpc(), tx_id=TX_ID)
    assert result["ok"] is True
    assert result["grade"] == "FULL"
    assert result["capabilities"]["validator_replay"] == "available"
    assert result["transaction"]["integrity"]["ok"] is True


def test_evidence_bundle_contains_reviewer_artifacts(tmp_path: Path):
    output = tmp_path / "evidence"
    result = EvidenceService(FullReplayRpc()).generate(TX_ID, output)
    assert result["capsule"]["integrity_ok"] is True
    assert result["replay"]["attempted"] == 2
    assert result["replay"]["successful"] == 2
    assert (output / "incident.genreplay").exists()
    assert (output / "evidence.json").exists()
    assert (output / "timeline.json").exists()
    assert (output / "explanation.json").exists()
    assert (output / "replays" / "round-000.json").exists()
    assert (output / "replays" / "round-001.json").exists()
