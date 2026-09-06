from pathlib import Path

from genreplay.capsule import Capsule
from genreplay.diffing import diff_capsules, json_diff
from genreplay.export import export_pytest
from genreplay.util import canonical_json_bytes

from .helpers import TX_ID


def cap(status: str) -> Capsule:
    return Capsule.build(
        tool_version="0.1.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"chain_id": 61999},
        files={
            "transaction/receipt.json": b"{}\n",
            "analysis/summary.json": canonical_json_bytes({"status": status}),
            "capture/issues.json": b"[]\n",
        },
    )


def test_json_diff_reports_nested_change():
    changes = json_diff({"a": {"b": 1}}, {"a": {"b": 2}})
    assert changes == [{"path": "$.a.b", "kind": "changed", "before": 1, "after": 2}]


def test_capsule_diff_compares_analysis():
    result = diff_capsules(cap("Accepted"), cap("Finalized"))
    assert any(item["path"] == "$.status" for item in result["analysis"])


def test_exported_test_contains_identity(tmp_path: Path):
    capsule_path = tmp_path / "incident.genreplay"
    cap("Finalized").write(capsule_path)
    output = export_pytest(capsule_path, tmp_path / "test_incident.py")
    text = output.read_text()
    assert TX_ID in text
    assert "GENREPLAY_RPC" in text
    assert "verify_integrity" in text
    assert (tmp_path / "replays" / f"{TX_ID[2:10]}.genreplay").exists()
    assert "Path(__file__).parent" in text
