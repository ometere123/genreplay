import json
import zipfile
from pathlib import Path

import pytest

from genreplay.capsule import Capsule
from genreplay.errors import CapsuleError

from .helpers import TX_ID


def make_capsule() -> Capsule:
    return Capsule.build(
        tool_version="0.1.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"chain_id": 61999, "rpc_url": "https://studio.genlayer.com/api"},
        files={"transaction/receipt.json": b'{"id":"x"}\n', "x.txt": b"hello\n"},
    )


def test_round_trip(tmp_path: Path):
    path = tmp_path / "x.genreplay"
    make_capsule().write(path)
    loaded = Capsule.load(path)
    assert loaded.manifest.tx_id == TX_ID
    assert loaded.read_json("transaction/receipt.json")["id"] == "x"


def test_integrity_passes():
    assert make_capsule().verify_integrity()["ok"] is True


def test_missing_declared_file_fails(tmp_path: Path):
    path = tmp_path / "bad.genreplay"
    cap = make_capsule()
    cap.write(path)
    manifest = cap.manifest.to_dict()
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("transaction/receipt.json", b'{"id":"x"}\n')
    with pytest.raises(CapsuleError, match="missing declared file"):
        Capsule.load(path)


def test_digest_mismatch_fails(tmp_path: Path):
    path = tmp_path / "bad.genreplay"
    cap = make_capsule()
    cap.write(path)
    with zipfile.ZipFile(path, "r") as original:
        manifest = original.read("manifest.json")
        receipt = original.read("transaction/receipt.json")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", manifest)
        zf.writestr("transaction/receipt.json", receipt)
        zf.writestr("x.txt", b"tampered")
    with pytest.raises(CapsuleError, match="digest mismatch"):
        Capsule.load(path)


def test_zip_timestamps_are_deterministic(tmp_path: Path):
    a = tmp_path / "a.genreplay"
    b = tmp_path / "b.genreplay"
    cap = make_capsule()
    cap.write(a)
    cap.write(b)
    assert a.read_bytes() == b.read_bytes()


def test_read_missing_file_has_clear_error():
    with pytest.raises(CapsuleError, match="does not contain"):
        make_capsule().read_bytes("nope")
