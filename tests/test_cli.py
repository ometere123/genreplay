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
    assert "0.1.0" in result.stdout


def test_verify_and_inspect_commands(tmp_path: Path):
    cap = Capsule.build(
        tool_version="0.1.0",
        captured_at="2026-09-06T00:00:00Z",
        tx_id=TX_ID,
        capture_level="protocol",
        network={"chain_id": 61999, "preset": "studionet"},
        files={
            "transaction/receipt.json": b"{}\n",
            "analysis/summary.json": canonical_json_bytes(
                {
                    "status": "Finalized",
                    "execution_result": "FinishedWithReturn",
                    "successful": True,
                    "round_count": 0,
                    "warnings": [],
                }
            ),
            "capture/issues.json": b"[]\n",
        },
    )
    path = tmp_path / "x.genreplay"
    cap.write(path)
    verify = run_cli("verify", str(path), "--json")
    assert verify.returncode == 0
    assert json.loads(verify.stdout)["ok"] is True
    inspect = run_cli("inspect", str(path))
    assert inspect.returncode == 0
    assert "successful  : True" in inspect.stdout
