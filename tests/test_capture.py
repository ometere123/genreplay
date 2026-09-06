from pathlib import Path

from genreplay.capture import CaptureService

from .helpers import SOURCE_B64, TX_ID, lifecycle, receipt, trace


class FakeCaptureRpc:
    endpoint = "https://studio.genlayer.com/api"

    def __init__(self, *, trace_failure: bool = False):
        self.trace_failure = trace_failure
        self.code_calls = []

    def chain_id(self):
        return 61999

    def get_transaction_receipt(self, tx_id):
        assert tx_id == TX_ID
        return receipt(rounds=2)

    def get_transaction_lifecycle(self, tx_id, *, timestamp=None):
        return lifecycle()

    def debug_trace_transaction(self, tx_id, *, round_number=0):
        if self.trace_failure and round_number == 1:
            raise RuntimeError("trace pruned")
        return trace(eq_outputs=[f"0x0{round_number + 1}"])

    def get_contract_code(self, address, *, block_number=None, status=None):
        self.code_calls.append((address, block_number, status))
        return SOURCE_B64

    def get_contract_state(self, address, *, block_number=None, status=None):
        return "0xcafe"

    def get_contract_schema_for_code(self, code_base64):
        assert code_base64 == SOURCE_B64
        return {"ctor": {"params": []}, "methods": {}}


class FallbackCaptureRpc(FakeCaptureRpc):
    def get_contract_code(self, address, *, block_number=None, status=None):
        self.code_calls.append((address, block_number, status))
        if block_number is not None:
            raise RuntimeError("historical code pruned")
        return SOURCE_B64

    def get_contract_state(self, address, *, block_number=None, status=None):
        if block_number is not None:
            raise RuntimeError("historical state pruned")
        return "0xbeef"


def test_capture_contains_protocol_evidence(tmp_path: Path):
    rpc = FakeCaptureRpc()
    cap = CaptureService(rpc).capture(TX_ID)
    assert cap.has("transaction/receipt.json")
    assert cap.has("transaction/lifecycle.json")
    assert cap.has("traces/round-000.json")
    assert cap.has("traces/round-001.json")
    assert cap.has("contract/source.py")
    assert cap.has("contract/schema.json")
    assert cap.has("contract/state.hex")
    assert cap.manifest.network["historical_state_block"] == "0x65"
    assert rpc.code_calls[0][1] == "0x65"
    assert cap.verify_integrity()["ok"]


def test_capture_records_partial_trace_failure():
    cap = CaptureService(FakeCaptureRpc(trace_failure=True)).capture(TX_ID)
    issues = cap.read_json("capture/issues.json")
    assert any(item["stage"] == "trace_round_1" for item in issues)
    assert cap.has("traces/round-000.json")
    assert not cap.has("traces/round-001.json")


def test_capture_can_skip_traces():
    cap = CaptureService(FakeCaptureRpc()).capture(TX_ID, include_traces=False)
    assert cap.trace_rounds() == []


def test_capture_rejects_bad_hash():
    try:
        CaptureService(FakeCaptureRpc()).capture("0x1234")
    except ValueError as exc:
        assert "32-byte" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_capture_records_historical_fallbacks():
    cap = CaptureService(FallbackCaptureRpc()).capture(TX_ID)
    issues = {item["stage"] for item in cap.read_json("capture/issues.json")}
    assert "contract_code_fallback" in issues
    assert "contract_state_fallback" in issues
    assert cap.has("contract/source.py")
    assert cap.read_bytes("contract/state.hex") == b"0xbeef\n"
