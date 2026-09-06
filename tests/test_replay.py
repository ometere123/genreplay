from dataclasses import replace

import pytest

from genreplay.capsule import Capsule
from genreplay.errors import ReplayError
from genreplay.models import ReplayScenario
from genreplay.replay import ReplayEngine, replay_signature, scenario_from_capsule
from genreplay.util import canonical_json_bytes

from .helpers import TX_ID, receipt, trace


def make_capsule(eq_outputs=None):
    return Capsule.build(
        tool_version="0.1.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"rpc_url": "http://localhost:4000/api", "historical_state_block": "0x65"},
        files={
            "transaction/receipt.json": canonical_json_bytes(receipt()),
            "traces/round-000.json": canonical_json_bytes(trace(eq_outputs=eq_outputs)),
            "analysis/summary.json": b"{}\n",
            "capture/issues.json": b"[]\n",
        },
    )


class FakeReplayRpc:
    endpoint = "http://localhost:4000/api"

    def __init__(self):
        self.requests = []

    def gen_call(self, request):
        self.requests.append(request)
        count = len(request.get("leader_results", []))
        return {
            "data": "0x00",
            "eqOutputs": [],
            "status": {"code": 0, "message": "success"},
            "stdout": "",
            "stderr": "",
            "events": [],
            "messages": [],
            "nondetDisagreementCallNo": 1 if count >= 2 else None,
        }


def test_scenario_uses_historical_inputs():
    scenario = scenario_from_capsule(make_capsule(), round_number=0)
    assert scenario.data == "0xdeadbeef"
    assert scenario.block_number == "0x65"
    assert scenario.leader_results == ["0x01", "0x02"]
    assert scenario.value == "0x0"


def test_replay_request_enters_validator_mode():
    rpc = FakeReplayRpc()
    scenario = scenario_from_capsule(make_capsule())
    result = ReplayEngine(rpc).run(scenario)
    assert rpc.requests[0]["leader_results"] == ["0x01", "0x02"]
    assert result.signature["nondet_disagreement_call"] == 1


def test_missing_trace_rejected():
    cap = make_capsule()
    with pytest.raises(ReplayError, match="no trace for round 2"):
        scenario_from_capsule(cap, round_number=2)


def test_empty_eq_outputs_rejected():
    with pytest.raises(ReplayError, match="no equivalence outputs"):
        scenario_from_capsule(make_capsule(eq_outputs=[]))


def test_scenario_without_leader_results_refused():
    rpc = FakeReplayRpc()
    scenario = ReplayScenario(
        version=1,
        source_tx_id=TX_ID,
        rpc_hint=None,
        from_address="0x1",
        to_address="0x2",
        call_type="write",
        data="0x00",
        leader_results=[],
    )
    with pytest.raises(ReplayError, match="no leader_results"):
        ReplayEngine(rpc).run(scenario)


def test_replay_signature_counts_messages():
    raw = {
        "status": {"code": 0, "message": "success"},
        "data": "0x00",
        "events": [{}, {}],
        "messages": [{}],
        "stderr": "oops",
        "nondetDisagreementCallNo": 0,
    }
    sig = replay_signature(raw)
    assert sig["event_count"] == 2
    assert sig["message_count"] == 1
    assert sig["stderr_present"] is True


def test_minimizer_only_keeps_exact_signature():
    class StableForTwo(FakeReplayRpc):
        def gen_call(self, request):
            self.requests.append(request)
            count = len(request.get("leader_results", []))
            disagreement = 1 if count >= 2 else None
            return {
                "data": "0x00",
                "status": {"code": 0, "message": "success"},
                "stderr": "",
                "events": [],
                "messages": [],
                "nondetDisagreementCallNo": disagreement,
            }

    scenario = scenario_from_capsule(make_capsule(eq_outputs=["0x01", "0x02", "0x03"]))
    best, trials = ReplayEngine(StableForTwo()).minimize_leader_prefix(scenario)
    assert len(best.leader_results) == 2
    assert any(t["prefix_length"] == 1 and not t["kept"] for t in trials)


def test_counterfactual_scenario_is_mutable_copy():
    scenario = scenario_from_capsule(make_capsule())
    altered = replace(scenario, to_address="0x" + "cc" * 20)
    assert altered.to_address != scenario.to_address
