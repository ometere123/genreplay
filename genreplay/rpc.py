from __future__ import annotations

import json
import urllib.error
import urllib.request
from itertools import count
from typing import Any

from .errors import RpcError
from .util import parse_int


class GenLayerRpcClient:
    """Small dependency-free JSON-RPC client for protocol/debugging surfaces.

    GenReplay intentionally calls the node RPC directly so replay capsules preserve
    the raw protocol objects instead of normalizing away consensus details.
    """

    def __init__(self, endpoint: str, *, timeout: float = 30.0, user_agent: str = "genreplay/0.1.0"):
        self.endpoint = endpoint
        self.timeout = timeout
        self.user_agent = user_agent
        self._ids = count(1)

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": next(self._ids),
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": self.user_agent},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RpcError(f"HTTP {exc.code} calling {method}: {detail[:500]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RpcError(f"transport error calling {method}: {exc}") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RpcError(f"invalid JSON-RPC response from {method}") from exc

        if not isinstance(decoded, dict):
            raise RpcError(f"invalid JSON-RPC envelope from {method}")
        if decoded.get("error") is not None:
            error = decoded["error"]
            if isinstance(error, dict):
                raise RpcError(
                    str(error.get("message", "JSON-RPC error")),
                    code=error.get("code"),
                    data=error.get("data"),
                )
            raise RpcError(str(error))
        if "result" not in decoded:
            raise RpcError(f"JSON-RPC response from {method} omitted result")
        return decoded["result"]

    def chain_id(self) -> int:
        return parse_int(self.call("eth_chainId"))

    def ping(self) -> Any:
        return self.call("gen_dbg_ping")

    def get_transaction_receipt(self, tx_id: str) -> dict[str, Any]:
        result = self.call("gen_getTransactionReceipt", [{"txId": tx_id}])
        if not isinstance(result, dict):
            raise RpcError("gen_getTransactionReceipt returned a non-object")
        return result

    def get_transaction_lifecycle(self, tx_id: str, *, timestamp: int | None = None) -> dict[str, Any]:
        request: dict[str, Any] = {"txId": tx_id}
        if timestamp is not None:
            request["timestamp"] = timestamp
        result = self.call("gen_getTransactionLifecycle", [request])
        if not isinstance(result, dict):
            raise RpcError("gen_getTransactionLifecycle returned a non-object")
        return result

    def debug_trace_transaction(self, tx_id: str, *, round_number: int = 0) -> dict[str, Any]:
        result = self.call(
            "gen_dbg_traceTransaction",
            [{"txID": tx_id, "round": round_number}],
        )
        if not isinstance(result, dict):
            raise RpcError("gen_dbg_traceTransaction returned a non-object")
        return result

    def get_contract_code(
        self,
        address: str,
        *,
        block_number: str | None = None,
        status: str | None = None,
    ) -> str:
        request: dict[str, Any] = {"address": address}
        if block_number is not None:
            request["blockNumber"] = block_number
        if status is not None:
            request["status"] = status
        result = self.call("gen_getContractCode", [request])
        if not isinstance(result, str):
            raise RpcError("gen_getContractCode returned a non-string")
        return result

    def get_contract_state(
        self,
        address: str,
        *,
        block_number: str | None = None,
        status: str | None = None,
    ) -> str:
        request: dict[str, Any] = {"address": address}
        if block_number is not None:
            request["blockNumber"] = block_number
        if status is not None:
            request["status"] = status
        result = self.call("gen_getContractState", [request])
        if not isinstance(result, str):
            raise RpcError("gen_getContractState returned a non-string")
        return result

    def get_contract_schema_for_code(self, code_base64: str) -> dict[str, Any]:
        result = self.call("gen_getContractSchema", [{"code": code_base64}])
        if not isinstance(result, dict):
            raise RpcError("gen_getContractSchema returned a non-object")
        return result

    def gen_call(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.call("gen_call", [request])
        if not isinstance(result, dict):
            raise RpcError("gen_call returned a non-object")
        return result

    def probe(self, method: str, params: list[Any] | None = None) -> dict[str, Any]:
        try:
            result = self.call(method, params)
            return {"supported": True, "result": result}
        except RpcError as exc:
            return {
                "supported": False,
                "error": str(exc),
                "code": exc.code,
            }
