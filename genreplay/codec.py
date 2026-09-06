from __future__ import annotations

from .errors import ReplayError
from .util import ensure_hex_prefix


class _RlpReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _take(self, length: int) -> bytes:
        if length < 0 or self.pos + length > len(self.data):
            raise ReplayError("truncated RLP in eqBlocksOutputs")
        value = self.data[self.pos : self.pos + length]
        self.pos += length
        return value

    def _length(self, length_of_length: int) -> int:
        raw = self._take(length_of_length)
        if not raw or raw[0] == 0:
            raise ReplayError("non-canonical RLP length in eqBlocksOutputs")
        return int.from_bytes(raw, "big")

    def item(self) -> bytes | list[bytes]:
        if self.pos >= len(self.data):
            raise ReplayError("unexpected end of RLP in eqBlocksOutputs")
        prefix = self._take(1)[0]
        if prefix <= 0x7F:
            return bytes([prefix])
        if prefix <= 0xB7:
            length = prefix - 0x80
            value = self._take(length)
            if length == 1 and value and value[0] <= 0x7F:
                raise ReplayError("non-canonical RLP string in eqBlocksOutputs")
            return value
        if prefix <= 0xBF:
            length = self._length(prefix - 0xB7)
            if length < 56:
                raise ReplayError("non-canonical long RLP string in eqBlocksOutputs")
            return self._take(length)
        if prefix <= 0xF7:
            payload_length = prefix - 0xC0
        else:
            payload_length = self._length(prefix - 0xF7)
            if payload_length < 56:
                raise ReplayError("non-canonical long RLP list in eqBlocksOutputs")

        end = self.pos + payload_length
        if end > len(self.data):
            raise ReplayError("truncated RLP list in eqBlocksOutputs")
        values: list[bytes] = []
        while self.pos < end:
            value = self.item()
            if isinstance(value, list):
                raise ReplayError("nested RLP list is invalid for eqBlocksOutputs")
            values.append(value)
        if self.pos != end:
            raise ReplayError("RLP list length mismatch in eqBlocksOutputs")
        return values


def decode_eq_blocks_outputs(value: str) -> list[str]:
    """Decode consensus `eqBlocksOutputs` into `gen_call.leader_results` values.

    GenLayer protocol tooling encodes this receipt field as RLP of
    ``[*eq_outputs, b"padded"]``. The sentinel is accounting padding and is not
    an equivalence output, so it is stripped only when it is the final item.
    """
    if not isinstance(value, str) or not value.strip():
        return []
    raw_hex = value.strip()
    if raw_hex.startswith(("0x", "0X")):
        raw_hex = raw_hex[2:]
    if not raw_hex:
        return []
    if len(raw_hex) % 2:
        raise ReplayError("eqBlocksOutputs has odd-length hex")
    try:
        encoded = bytes.fromhex(raw_hex)
    except ValueError as exc:
        raise ReplayError("eqBlocksOutputs is not valid hex") from exc

    reader = _RlpReader(encoded)
    decoded = reader.item()
    if reader.pos != len(encoded):
        raise ReplayError("trailing bytes after eqBlocksOutputs RLP")
    if not isinstance(decoded, list):
        raise ReplayError("eqBlocksOutputs must decode to an RLP list")
    if decoded and decoded[-1] == b"padded":
        decoded = decoded[:-1]
    return [ensure_hex_prefix(item.hex()) for item in decoded]
