import json
import subprocess
import sys
from pathlib import Path

from genreplay.capsule import Capsule
from genreplay.util import canonical_json_bytes

from .helpers import TX_ID


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "genreplay", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_networks_command():
    result = run_cli("networks")
    assert result.returncode == 0
    assert "studionet" in result.stdout
    assert "61999" in result.stdout


def test_version_command():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "0.2.0" in result.stdout


def _write_capsule(tmp_path: Path) -> Path:
    cap = Capsule.build(
        tool_version="0.2.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"chain_id": 61999, "preset": "studionet"},
        files={
            "transaction/receipt.json": canonical_json_bytes(
                {
                    "id": TX_ID,
                    "statusName": "Finalized",
                    "txExecutionResultName": "FinishedWithReturn",
                    "messages": [],
                }
            ),
            "analysis/summary.json": canonical_json_bytes(
                {
                    "status": "Finalized",
                    "execution_result": "FinishedWithReturn",
                    "successful": True,
                    "round_count": 0,
                    "rounds": [],
                    "warnings": [],
                }
            ),
            "capture/issues.json": b"[]\n",
        },
    )
    path = tmp_path / "x.genreplay"
    cap.write(path)
    return path


def test_verify_and_inspect_commands(tmp_path: Path):
    path = _write_capsule(tmp_path)
    verify = run_cli("verify", str(path), "--json")
    assert verify.returncode == 0
    report = json.loads(verify.stdout)
    assert report["ok"] is True
    assert report["schema_version"] == 1
    inspect = run_cli("inspect", str(path))
    assert inspect.returncode == 0
    assert "successful  : True" in inspect.stdout


def test_timeline_and_explain_commands_emit_versioned_json(tmp_path: Path):
    path = _write_capsule(tmp_path)
    timeline = run_cli("timeline", str(path), "--json")
    assert timeline.returncode == 0
    assert json.loads(timeline.stdout)["schema_version"] == 1
    explain = run_cli("explain", str(path), "--json")
    assert explain.returncode == 0
    payload = json.loads(explain.stdout)
    assert payload["schema_version"] == 1
    assert payload["primary_cause"] == "CONSENSUS_AND_EXECUTION_SUCCEEDED"
