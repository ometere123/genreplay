from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CaptureIssue:
    stage: str
    message: str
    fatal: bool = False
    code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReplayScenario:
    version: int
    source_tx_id: str
    rpc_hint: str | None
    from_address: str
    to_address: str
    call_type: str
    data: str
    status: str | None = "accepted"
    block_number: str | None = None
    value: str | None = None
    leader_results: list[str] = field(default_factory=list)
    round_number: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReplayScenario":
        return cls(
            version=int(value.get("version", 1)),
            source_tx_id=str(value["source_tx_id"]),
            rpc_hint=value.get("rpc_hint"),
            from_address=str(value["from_address"]),
            to_address=str(value["to_address"]),
            call_type=str(value.get("call_type", "write")),
            data=str(value["data"]),
            status=value.get("status"),
            block_number=value.get("block_number"),
            value=value.get("value"),
            leader_results=[str(v) for v in value.get("leader_results", [])],
            round_number=int(value.get("round_number", 0)),
            notes=[str(v) for v in value.get("notes", [])],
        )

    def to_gen_call_request(self) -> dict[str, Any]:
        request: dict[str, Any] = {
            "from": self.from_address,
            "to": self.to_address,
            "type": self.call_type,
            "data": self.data,
        }
        if self.status:
            request["status"] = self.status
        if self.block_number:
            request["blockNumber"] = self.block_number
        if self.value:
            request["value"] = self.value
        if self.leader_results:
            request["leader_results"] = list(self.leader_results)
        return request


@dataclass(slots=True)
class ReplayResult:
    scenario: dict[str, Any]
    raw: dict[str, Any]
    signature: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
