from __future__ import annotations

import base64
from typing import Any, Protocol

from ._version import __version__
from .analysis import analyze_receipt
from .capsule import Capsule
from .models import CaptureIssue
from .networks import identify_network
from .util import canonical_json_bytes, hex_quantity, sha256_bytes, utc_now_iso, validate_tx_id


class CaptureRpc(Protocol):
    endpoint: str

    def chain_id(self) -> int: ...
    def get_transaction_receipt(self, tx_id: str) -> dict[str, Any]: ...
    def get_transaction_lifecycle(
        self, tx_id: str, *, timestamp: int | None = None
    ) -> dict[str, Any]: ...
    def debug_trace_transaction(
        self, tx_id: str, *, round_number: int = 0
    ) -> dict[str, Any]: ...
    def get_contract_code(
        self, address: str, *, block_number: str | None = None, status: str | None = None
    ) -> str: ...
    def get_contract_state(
        self, address: str, *, block_number: str | None = None, status: str | None = None
    ) -> str: ...
    def get_contract_schema_for_code(self, code_base64: str) -> dict[str, Any]: ...


class CaptureService:
    def __init__(self, rpc: CaptureRpc):
        self.rpc = rpc

    @staticmethod
    def _snapshot_block(receipt: dict[str, Any]) -> str | None:
        ranges = receipt.get("readStateBlockRanges") or []
        if not isinstance(ranges, list) or not ranges:
            return None
        first = ranges[0]
        if not isinstance(first, dict):
            return None
        for key in ("ProcessingBlock", "ProposalBlock", "ActivationBlock"):
            value = first.get(key)
            if value not in (None, "", 0, "0"):
                return hex_quantity(value)
        return None

    def capture(
        self,
        tx_id: str,
        *,
        include_traces: bool = True,
        include_contract: bool = True,
        include_state: bool = True,
    ) -> Capsule:
        tx_id = validate_tx_id(tx_id)
        issues: list[CaptureIssue] = []
        files: dict[str, bytes] = {}

        receipt = self.rpc.get_transaction_receipt(tx_id)
        files["transaction/receipt.json"] = canonical_json_bytes(receipt)

        try:
            chain_id = self.rpc.chain_id()
        except Exception as exc:  # capture should remain useful on partial RPCs
            chain_id = None
            issues.append(CaptureIssue("chain_id", str(exc)))

        lifecycle: dict[str, Any] | None = None
        try:
            lifecycle = self.rpc.get_transaction_lifecycle(tx_id)
            files["transaction/lifecycle.json"] = canonical_json_bytes(lifecycle)
        except Exception as exc:
            issues.append(CaptureIssue("lifecycle", str(exc)))

        traces: dict[int, dict[str, Any]] = {}
        round_data = receipt.get("roundData") or []
        round_numbers: list[int] = []
        if isinstance(round_data, list) and round_data:
            for index, item in enumerate(round_data):
                if isinstance(item, dict):
                    try:
                        round_numbers.append(int(item.get("round", index)))
                    except (TypeError, ValueError):
                        round_numbers.append(index)
        else:
            round_numbers = [0]

        if include_traces:
            for round_number in sorted(set(round_numbers)):
                try:
                    trace = self.rpc.debug_trace_transaction(tx_id, round_number=round_number)
                    traces[round_number] = trace
                    files[f"traces/round-{round_number:03d}.json"] = canonical_json_bytes(trace)
                except Exception as exc:
                    issues.append(CaptureIssue(f"trace_round_{round_number}", str(exc)))

        recipient = receipt.get("recipient")
        block_number = self._snapshot_block(receipt)
        code_b64: str | None = None
        code_status = "finalized" if str(receipt.get("statusName", "")).lower() == "finalized" else "accepted"
        if include_contract and isinstance(recipient, str) and recipient:
            attempts = [
                (block_number, code_status),
                (block_number, "accepted"),
                (None, code_status),
                (None, "accepted"),
            ]
            seen: set[tuple[str | None, str | None]] = set()
            used_candidate: tuple[str | None, str | None] | None = None
            first_candidate: tuple[str | None, str | None] | None = None
            for candidate in attempts:
                if candidate in seen:
                    continue
                seen.add(candidate)
                if first_candidate is None:
                    first_candidate = candidate
                try:
                    code_b64 = self.rpc.get_contract_code(
                        recipient,
                        block_number=candidate[0],
                        status=candidate[1],
                    )
                    if code_b64:
                        used_candidate = candidate
                        break
                except Exception as exc:
                    last_contract_error = exc
            if code_b64:
                if used_candidate != first_candidate:
                    issues.append(
                        CaptureIssue(
                            "contract_code_fallback",
                            f"historical/preferred source read unavailable; used {used_candidate}",
                        )
                    )
                files["contract/source.b64"] = code_b64.encode("ascii")
                try:
                    source = base64.b64decode(code_b64, validate=True)
                    files["contract/source.py"] = source
                    files["contract/source.sha256"] = (sha256_bytes(source) + "\n").encode("ascii")
                except Exception as exc:
                    issues.append(CaptureIssue("contract_decode", str(exc)))
                try:
                    schema = self.rpc.get_contract_schema_for_code(code_b64)
                    files["contract/schema.json"] = canonical_json_bytes(schema)
                except Exception as exc:
                    issues.append(CaptureIssue("contract_schema", str(exc)))
            else:
                issues.append(
                    CaptureIssue(
                        "contract_code",
                        str(locals().get("last_contract_error", "contract source unavailable")),
                    )
                )

        if include_state and isinstance(recipient, str) and recipient:
            state: str | None = None
            state_error: Exception | None = None
            state_attempts = [(block_number, "accepted"), (None, "accepted")]
            state_seen: set[tuple[str | None, str]] = set()
            state_used: tuple[str | None, str] | None = None
            state_first: tuple[str | None, str] | None = None
            for candidate in state_attempts:
                if candidate in state_seen:
                    continue
                state_seen.add(candidate)
                if state_first is None:
                    state_first = candidate
                try:
                    state = self.rpc.get_contract_state(
                        recipient,
                        block_number=candidate[0],
                        status=candidate[1],
                    )
                    state_used = candidate
                    break
                except Exception as exc:
                    state_error = exc
            if state is not None:
                files["contract/state.hex"] = (state + "\n").encode("ascii")
                if state_used != state_first:
                    issues.append(
                        CaptureIssue(
                            "contract_state_fallback",
                            f"historical state read unavailable; used {state_used}",
                        )
                    )
            elif state_error is not None:
                issues.append(CaptureIssue("contract_state", str(state_error)))

        analysis = analyze_receipt(
            receipt,
            lifecycle=lifecycle,
            traces=traces,
            contract_code_captured=code_b64 is not None,
        )
        files["analysis/summary.json"] = canonical_json_bytes(analysis)
        files["capture/issues.json"] = canonical_json_bytes([issue.to_dict() for issue in issues])

        network_name = identify_network(getattr(self.rpc, "endpoint", ""), chain_id)
        network = {
            "rpc_url": getattr(self.rpc, "endpoint", None),
            "chain_id": chain_id,
            "preset": network_name,
            "historical_state_block": block_number,
        }
        return Capsule.build(
            tool_version=__version__,
            captured_at=utc_now_iso(),
            tx_id=tx_id,
            capture_level="protocol",
            network=network,
            files=files,
        )
