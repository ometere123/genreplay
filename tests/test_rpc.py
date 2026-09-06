from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from genreplay.errors import RpcError
from genreplay.rpc import GenLayerRpcClient


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        Handler.calls.append(payload)
        method = payload["method"]
        if method == "fail":
            result = {"jsonrpc": "2.0", "id": payload["id"], "error": {"code": -32000, "message": "boom"}}
        elif method == "eth_chainId":
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": "0xf22f"}
        elif method == "gen_getTransactionReceipt":
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": {"id": "0x1"}}
        elif method == "gen_dbg_traceTransaction":
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": {"eq_outputs": ["0x01"]}}
        elif method == "gen_call":
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": {"status": {"code": 0}}}
        else:
            result = {"jsonrpc": "2.0", "id": payload["id"], "result": "pong"}
        raw = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def rpc_server():
    Handler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_chain_id_parses_hex(rpc_server):
    assert GenLayerRpcClient(rpc_server).chain_id() == 61999


def test_receipt_wrapper_uses_correct_parameter_name(rpc_server):
    client = GenLayerRpcClient(rpc_server)
    client.get_transaction_receipt("0xabc")
    call = Handler.calls[-1]
    assert call["method"] == "gen_getTransactionReceipt"
    assert call["params"] == [{"txId": "0xabc"}]


def test_trace_wrapper_uses_txID_and_round(rpc_server):
    client = GenLayerRpcClient(rpc_server)
    client.debug_trace_transaction("0xabc", round_number=2)
    call = Handler.calls[-1]
    assert call["params"] == [{"txID": "0xabc", "round": 2}]


def test_gen_call_passes_request(rpc_server):
    client = GenLayerRpcClient(rpc_server)
    result = client.gen_call({"type": "write", "leader_results": ["0x01"]})
    assert result["status"]["code"] == 0
    assert Handler.calls[-1]["params"][0]["leader_results"] == ["0x01"]


def test_rpc_error_preserves_code(rpc_server):
    with pytest.raises(RpcError) as exc_info:
        GenLayerRpcClient(rpc_server).call("fail")
    assert exc_info.value.code == -32000
    assert "boom" in str(exc_info.value)
