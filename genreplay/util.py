from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_hex_prefix(value: str) -> str:
    if value.startswith("0x"):
        return value
    return "0x" + value


def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    return int(value)


def hex_quantity(value: Any) -> str:
    return hex(parse_int(value))


def validate_tx_id(tx_id: str) -> str:
    tx_id = tx_id.strip().lower()
    if not tx_id.startswith("0x") or len(tx_id) != 66:
        raise ValueError("transaction id must be a 32-byte 0x-prefixed hash")
    try:
        int(tx_id[2:], 16)
    except ValueError as exc:
        raise ValueError("transaction id contains non-hex characters") from exc
    return tx_id
