from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .capsule import Capsule
from .errors import ReplayError
from .models import RegressionSpec, ReplayProvenance, ReplayScenario
from .util import canonical_json_bytes, ensure_hex_prefix, sha256_bytes

REGRESSION_SCHEMA_VERSION = 1
DEFAULT_INVARIANT_FIELDS = [
    "status_code", "nondet_disagreement_call", "return_data_sha256", "stderr_present",
    "event_count", "message_count",
]


def normalise_regression_signature(signature: dict[str, Any]) -> dict[str, Any]:
    """Stable signature: status wording is deliberately not an invariant."""
    value = signature.get("return_data")
    return {
        "status_code": signature.get("status_code"),
        "nondet_disagreement_call": signature.get("nondet_disagreement_call"),
        "return_data_sha256": sha256_bytes(("" if value is None else str(value)).encode()),
        "stderr_present": bool(signature.get("stderr_present")),
        "event_count": int(signature.get("event_count", 0)),
        "message_count": int(signature.get("message_count", 0)),
    }


def _load_baseline(source: Path, baseline: str | Path | None) -> dict[str, Any]:
    if baseline is not None:
        path = Path(baseline)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReplayError(f"invalid replay baseline {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ReplayError("replay baseline must be a JSON object")
        return data
    if not source.is_dir():
        raise ReplayError("behavioural export needs --baseline or an evidence directory")
    candidates: list[dict[str, Any]] = []
    for path in sorted((source / "replays").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("ok") is True and isinstance(data.get("signature"), dict):
            candidates.append(data)
    if not candidates:
        raise ReplayError("evidence directory contains no successful replay baseline")
    if len(candidates) != 1:
        raise ReplayError("multiple successful replays: select the baseline explicitly with --baseline")
    return candidates[0]


def _capsule_path(source: Path) -> Path:
    capsule = source / "incident.genreplay" if source.is_dir() else source
    if not capsule.is_file():
        raise ReplayError(f"capsule does not exist: {capsule}")
    return capsule


def _build_spec(capsule_path: Path, baseline: dict[str, Any], fields: list[str]) -> RegressionSpec:
    capsule = Capsule.load(capsule_path)
    scenario_data = baseline.get("scenario")
    signature = baseline.get("signature")
    if not isinstance(scenario_data, dict) or not isinstance(signature, dict):
        raise ReplayError("replay baseline must contain scenario and signature objects")
    scenario = ReplayScenario.from_dict(scenario_data)
    if scenario.source_tx_id != capsule.manifest.tx_id or not scenario.leader_results:
        raise ReplayError("replay baseline does not bind usable leader results to this capsule")
    if not fields or any(item not in DEFAULT_INVARIANT_FIELDS for item in fields):
        raise ReplayError("invariant fields must be stable signature fields")
    mode = baseline.get("source")
    if mode not in {"round-trace", "receipt.eqBlocksOutputs"}:
        mode = "receipt.eqBlocksOutputs" if scenario.round_number is None else "round-trace"
    if (mode == "round-trace") != (scenario.round_number is not None):
        raise ReplayError("baseline provenance conflicts with round attribution")
    chain_id = capsule.manifest.network.get("chain_id")
    try:
        chain_id = None if chain_id is None else int(chain_id)
    except (TypeError, ValueError) as exc:
        raise ReplayError("capsule chain_id is invalid") from exc
    provenance = ReplayProvenance(
        source_tx_id=capsule.manifest.tx_id, source_mode=str(mode), round_number=scenario.round_number,
        source_capsule_digest=sha256_bytes(capsule_path.read_bytes()), network=dict(capsule.manifest.network),
        chain_id=chain_id, rpc_hint=scenario.rpc_hint, from_address=scenario.from_address,
        target_address=scenario.to_address, calldata_digest=sha256_bytes(ensure_hex_prefix(scenario.data).encode()),
        value=scenario.value, historical_block_anchor=scenario.block_number, status_anchor=scenario.status,
        leader_results_digest=sha256_bytes(canonical_json_bytes(scenario.leader_results)),
        leader_results_count=len(scenario.leader_results),
    )
    normalised = normalise_regression_signature(signature)
    return RegressionSpec(REGRESSION_SCHEMA_VERSION, provenance, {key: normalised[key] for key in fields}, fields)


def export_pytest(source: str | Path, destination: str | Path, *, baseline: str | Path | None = None,
                  invariant_fields: list[str] | None = None) -> Path:
    """Export a fail-closed provenance-preserving behavioural pytest regression."""
    source_path = Path(source).resolve()
    capsule_path = _capsule_path(source_path)
    spec = _build_spec(capsule_path, _load_baseline(source_path, baseline), invariant_fields or list(DEFAULT_INVARIANT_FIELDS))
    capsule = Capsule.load(capsule_path)
    tx_short = capsule.manifest.tx_id[2:10]
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    replay_dir = target.parent / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_name = f"{tx_short}.genreplay"
    shutil.copyfile(capsule_path, replay_dir / replay_name)
    spec_literal = repr(spec.to_dict())
    code = f'''"""Behavioural GenReplay regression generated from {capsule.manifest.tx_id}."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import pytest
from genreplay.capsule import Capsule
from genreplay.replay import ReplayEngine, scenario_from_capsule, scenario_from_receipt_outputs
from genreplay.rpc import GenLayerRpcClient
CAPSULE = Path(__file__).parent / "replays" / "{replay_name}"
SPEC = {spec_literal}
def _normalise(signature):
    value = signature.get("return_data")
    return {{"status_code": signature.get("status_code"), "nondet_disagreement_call": signature.get("nondet_disagreement_call"), "return_data_sha256": hashlib.sha256(("" if value is None else str(value)).encode()).hexdigest(), "stderr_present": bool(signature.get("stderr_present")), "event_count": int(signature.get("event_count", 0)), "message_count": int(signature.get("message_count", 0))}}
def test_capsule_{tx_short}_integrity():
    assert Capsule.load(CAPSULE).verify_integrity()["ok"] is True
def test_capsule_{tx_short}_source_identity():
    capsule = Capsule.load(CAPSULE)
    assert capsule.manifest.tx_id == SPEC["provenance"]["source_tx_id"]
    assert capsule.manifest.network.get("chain_id") == SPEC["provenance"]["chain_id"]
def test_capsule_{tx_short}_replay_provenance():
    provenance = SPEC["provenance"]
    assert (provenance["source_mode"] == "round-trace") == (provenance["round_number"] is not None)
@pytest.mark.skipif(not os.getenv("GENREPLAY_RPC"), reason="set GENREPLAY_RPC for live validator replay")
def test_capsule_{tx_short}_validator_replay_matches_frozen_signature():
    capsule = Capsule.load(CAPSULE)
    provenance = SPEC["provenance"]
    scenario = scenario_from_capsule(capsule, round_number=provenance["round_number"]) if provenance["source_mode"] == "round-trace" else scenario_from_receipt_outputs(capsule)
    actual = _normalise(ReplayEngine(GenLayerRpcClient(os.environ["GENREPLAY_RPC"])).run(scenario).signature)
    assert {{key: actual[key] for key in SPEC["invariant_fields"]}} == SPEC["expected_signature"]
'''
    target.write_text(code, encoding="utf-8")
    return target
