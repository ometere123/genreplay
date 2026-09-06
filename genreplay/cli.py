from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .capsule import Capsule
from .capture import CaptureService
from .diffing import diff_capsules
from .doctor import run_doctor
from .errors import GenReplayError
from .evidence import EvidenceService
from .export import export_pytest
from .models import ReplayScenario
from .networks import PRESETS, resolve_rpc
from .replay import ReplayEngine, scenario_from_capsule
from .report import build_timeline, explain_capsule
from .rpc import GenLayerRpcClient
from .util import pretty_json


def _rpc_from_args(args: argparse.Namespace, *, rpc_hint: str | None = None) -> GenLayerRpcClient:
    if getattr(args, "rpc", None):
        endpoint = args.rpc
    elif getattr(args, "network", None):
        endpoint, _ = resolve_rpc(network=args.network, rpc_url=None)
    elif rpc_hint:
        endpoint = rpc_hint
    else:
        endpoint, _ = resolve_rpc(network="studionet", rpc_url=None)
    return GenLayerRpcClient(endpoint, timeout=float(getattr(args, "timeout", 30.0)))


def _print_json(value: Any) -> None:
    sys.stdout.write(pretty_json(value))


def _print_inspect(capsule: Capsule) -> None:
    summary = capsule.read_json("analysis/summary.json") if capsule.has("analysis/summary.json") else {}
    issues = capsule.read_json("capture/issues.json") if capsule.has("capture/issues.json") else []
    print(f"GenReplay capsule v{capsule.manifest.version}")
    print(f"transaction : {capsule.manifest.tx_id}")
    print(f"captured    : {capsule.manifest.captured_at}")
    print(f"network     : {capsule.manifest.network.get('preset') or 'custom'}")
    print(f"chain id    : {capsule.manifest.network.get('chain_id')}")
    print(f"status      : {summary.get('status', 'unknown')}")
    print(f"execution   : {summary.get('execution_result', 'unknown')}")
    print(f"successful  : {summary.get('successful', False)}")
    print(f"rounds      : {summary.get('round_count', len(capsule.trace_rounds()))}")
    print(f"trace rounds: {', '.join(map(str, capsule.trace_rounds())) or 'none'}")
    print(f"files       : {len(capsule.manifest.files)}")
    warnings = summary.get("warnings") or []
    print(f"warnings    : {len(warnings)}")
    for warning in warnings:
        if isinstance(warning, dict):
            severity = warning.get("severity", "info").upper()
            print(f"  - {severity:6} {warning.get('code')}: {warning.get('message')}")
    if issues:
        print(f"capture gaps: {len(issues)}")
        for issue in issues:
            if isinstance(issue, dict):
                print(f"  - {issue.get('stage')}: {issue.get('message')}")


def _load_scenario(path: str | Path) -> ReplayScenario:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GenReplayError("scenario JSON must be an object")
    return ReplayScenario.from_dict(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genreplay",
        description="Capture and counterfactually replay GenLayer consensus executions.",
    )
    parser.add_argument("--version", action="version", version=f"genreplay {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    networks = sub.add_parser("networks", help="list built-in GenLayer RPC presets")
    networks.set_defaults(handler=cmd_networks)

    doctor = sub.add_parser("doctor", help="probe GenReplay compatibility and replay capability")
    doctor.add_argument("--network", choices=sorted(PRESETS))
    doctor.add_argument("--rpc")
    doctor.add_argument("--timeout", type=float, default=10.0)
    doctor.add_argument("--tx-id", help="prove capture and validator replay using this real transaction")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=cmd_doctor)

    capture = sub.add_parser("capture", help="capture a live transaction into a .genreplay capsule")
    capture.add_argument("tx_id")
    capture.add_argument("-o", "--output")
    capture.add_argument("--network", choices=sorted(PRESETS))
    capture.add_argument("--rpc")
    capture.add_argument("--timeout", type=float, default=30.0)
    capture.add_argument("--no-traces", action="store_true")
    capture.add_argument("--no-contract", action="store_true")
    capture.add_argument("--no-state", action="store_true")
    capture.add_argument("--json", action="store_true")
    capture.set_defaults(handler=cmd_capture)

    evidence = sub.add_parser("evidence", help="generate a reviewer-ready live transaction evidence bundle")
    evidence.add_argument("tx_id")
    evidence.add_argument("-o", "--output", required=True)
    evidence.add_argument("--network", choices=sorted(PRESETS))
    evidence.add_argument("--rpc")
    evidence.add_argument("--timeout", type=float, default=60.0)
    evidence.add_argument("--no-contract", action="store_true")
    evidence.add_argument("--no-state", action="store_true")
    evidence.add_argument("--no-replay", action="store_true")
    evidence.add_argument("--json", action="store_true")
    evidence.set_defaults(handler=cmd_evidence)

    inspect = sub.add_parser("inspect", help="summarize a replay capsule")
    inspect.add_argument("capsule")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--no-verify", action="store_true")
    inspect.set_defaults(handler=cmd_inspect)

    verify = sub.add_parser("verify", help="verify capsule SHA-256 integrity")
    verify.add_argument("capsule")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(handler=cmd_verify)

    timeline = sub.add_parser("timeline", help="show consensus rounds and round-to-round changes")
    timeline.add_argument("capsule")
    timeline.add_argument("--json", action="store_true")
    timeline.set_defaults(handler=cmd_timeline)

    explain = sub.add_parser("explain", help="derive a deterministic explanation from protocol evidence")
    explain.add_argument("capsule")
    explain.add_argument("--json", action="store_true")
    explain.set_defaults(handler=cmd_explain)

    replay = sub.add_parser("replay", help="run captured leader outputs through validator-mode gen_call")
    replay.add_argument("capsule")
    replay.add_argument("--round", type=int, default=0)
    replay.add_argument("--all-rounds", action="store_true")
    replay.add_argument("--network", choices=sorted(PRESETS))
    replay.add_argument("--rpc")
    replay.add_argument("--timeout", type=float, default=60.0)
    replay.add_argument("--target", help="counterfactual target contract address")
    replay.add_argument("--sender", help="counterfactual sender address")
    replay.add_argument("--block", help="counterfactual block number")
    replay.add_argument("--latest-state", action="store_true", help="omit historical block pinning")
    replay.add_argument("--status", choices=["accepted", "finalized"])
    replay.add_argument("--json", action="store_true")
    replay.set_defaults(handler=cmd_replay)

    fork = sub.add_parser("fork", help="export a mutable counterfactual replay scenario")
    fork.add_argument("capsule")
    fork.add_argument("-o", "--output", required=True)
    fork.add_argument("--round", type=int, default=0)
    fork.add_argument("--target")
    fork.add_argument("--sender")
    fork.add_argument("--block")
    fork.add_argument("--latest-state", action="store_true", help="omit historical block pinning")
    fork.add_argument("--status", choices=["accepted", "finalized"])
    fork.add_argument("--data", help="override 0x-encoded call data")
    fork.add_argument("--rpc", help="store a counterfactual RPC hint")
    fork.set_defaults(handler=cmd_fork)

    run = sub.add_parser("run-scenario", help="execute a saved scenario with validator-mode gen_call")
    run.add_argument("scenario")
    run.add_argument("--network", choices=sorted(PRESETS))
    run.add_argument("--rpc")
    run.add_argument("--timeout", type=float, default=60.0)
    run.add_argument("--json", action="store_true")
    run.set_defaults(handler=cmd_run_scenario)

    minimize = sub.add_parser("minimize", help="conservatively reduce leader-results prefix")
    minimize.add_argument("scenario")
    minimize.add_argument("-o", "--output", required=True)
    minimize.add_argument("--network", choices=sorted(PRESETS))
    minimize.add_argument("--rpc")
    minimize.add_argument("--timeout", type=float, default=60.0)
    minimize.add_argument("--trials-output")
    minimize.set_defaults(handler=cmd_minimize)

    diff = sub.add_parser("diff", help="compare two replay capsules")
    diff.add_argument("left")
    diff.add_argument("right")
    diff.add_argument("--full", action="store_true")
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(handler=cmd_diff)

    export = sub.add_parser("export-test", help="export a capsule-backed pytest regression")
    export.add_argument("capsule")
    export.add_argument("-o", "--output", required=True)
    export.set_defaults(handler=cmd_export_test)

    return parser


def cmd_networks(args: argparse.Namespace) -> int:
    for preset in PRESETS.values():
        print(f"{preset.name:18} chain={preset.chain_id:<6} {preset.rpc_url}")
        print(f"{'':18} {preset.purpose}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    rpc = _rpc_from_args(args)
    report = run_doctor(rpc, tx_id=args.tx_id)
    if args.json:
        _print_json(report)
    else:
        print(f"endpoint : {report['endpoint']}")
        print(f"chain id : {report['chain_id']}")
        print(f"grade    : {report['grade']}")
        for check in report["checks"]:
            state = "PASS" if check["ok"] else "FAIL"
            detail = check.get("value", check.get("error", ""))
            print(f"{state} {check['name']}: {detail}")
        if args.tx_id:
            print("capabilities:")
            for name, value in report["capabilities"].items():
                if name != "capture_issue_stages":
                    print(f"  {name:18} {value}")
    return 0 if report["ok"] else 2


def cmd_capture(args: argparse.Namespace) -> int:
    rpc = _rpc_from_args(args)
    capsule = CaptureService(rpc).capture(
        args.tx_id,
        include_traces=not args.no_traces,
        include_contract=not args.no_contract,
        include_state=not args.no_state,
    )
    output = Path(args.output or f"{capsule.manifest.tx_id[2:14]}.genreplay")
    capsule.write(output)
    result = {
        "output": str(output),
        "tx_id": capsule.manifest.tx_id,
        "files": len(capsule.manifest.files),
        "integrity": capsule.verify_integrity(),
        "analysis": capsule.read_json("analysis/summary.json"),
        "capture_issues": capsule.read_json("capture/issues.json"),
    }
    if args.json:
        _print_json(result)
    else:
        print(f"captured {capsule.manifest.tx_id} -> {output}")
        print(f"files: {result['files']}; capture gaps: {len(result['capture_issues'])}")
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    rpc = _rpc_from_args(args)
    result = EvidenceService(rpc).generate(
        args.tx_id,
        args.output,
        include_contract=not args.no_contract,
        include_state=not args.no_state,
        replay_rounds=not args.no_replay,
    )
    if args.json:
        _print_json(result)
    else:
        print(f"evidence bundle: {Path(args.output)}")
        print(f"transaction    : {result['tx_id']}")
        print(f"status         : {result['consensus']['status']}")
        print(f"execution      : {result['consensus']['execution_result']}")
        print(f"rounds         : {result['consensus']['round_count']}")
        print(
            "replays        : "
            f"{result['replay']['successful']}/{result['replay']['attempted']} successful"
        )
        print(f"primary cause  : {result['primary_cause']}")
    return 0 if result["capsule"]["integrity_ok"] else 3


def cmd_inspect(args: argparse.Namespace) -> int:
    capsule = Capsule.load(args.capsule, verify=not args.no_verify)
    if args.json:
        _print_json(
            {
                "schema_version": 1,
                "manifest": capsule.manifest.to_dict(),
                "analysis": (
                    capsule.read_json("analysis/summary.json")
                    if capsule.has("analysis/summary.json")
                    else None
                ),
                "capture_issues": (
                    capsule.read_json("capture/issues.json")
                    if capsule.has("capture/issues.json")
                    else []
                ),
                "integrity": capsule.verify_integrity(),
            }
        )
    else:
        _print_inspect(capsule)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    capsule = Capsule.load(args.capsule, verify=False)
    report = capsule.verify_integrity()
    report["schema_version"] = 1
    if args.json:
        _print_json(report)
    else:
        print("PASS" if report["ok"] else "FAIL", f"{report['file_count']} files checked")
        for error in report["errors"]:
            print(" -", error)
    return 0 if report["ok"] else 3


def cmd_timeline(args: argparse.Namespace) -> int:
    result = build_timeline(Capsule.load(args.capsule))
    if args.json:
        _print_json(result)
    else:
        print(f"transaction : {result['tx_id']}")
        print(f"status      : {result['status']}")
        print(f"execution   : {result['execution_result']}")
        print(f"rounds      : {result['round_count']}")
        for item in result["rounds"]:
            trace = item["trace"]
            print(
                f"round {item['round']}: leader={item['leader']} committee={item['committee_size']} "
                f"revealed={item['votes_revealed']} eq_outputs={trace['eq_output_count']} "
                f"disagreement={trace['nondet_disagreement_call']}"
            )
        for transition in result["transitions"]:
            changed = ", ".join(transition["changed"]) or "none"
            print(
                f"change {transition['from_round']} -> {transition['to_round']}: {changed}"
            )
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    result = explain_capsule(Capsule.load(args.capsule))
    if args.json:
        _print_json(result)
    else:
        print(f"transaction    : {result['tx_id']}")
        print(f"primary cause  : {result['primary_cause']}")
        print(f"conclusion     : {result['conclusion']}")
        print("evidence:")
        for item in result["evidence"]:
            print(f"  - {item}")
        print(f"note           : {result['note']}")
    return 0


def _apply_scenario_overrides(scenario: ReplayScenario, args: argparse.Namespace) -> ReplayScenario:
    if getattr(args, "target", None):
        scenario.to_address = args.target
    if getattr(args, "sender", None):
        scenario.from_address = args.sender
    if getattr(args, "latest_state", False):
        scenario.block_number = None
    elif getattr(args, "block", None):
        scenario.block_number = args.block
    if getattr(args, "status", None):
        scenario.status = args.status
    if getattr(args, "data", None):
        scenario.data = args.data
    if getattr(args, "rpc", None):
        scenario.rpc_hint = args.rpc
    return scenario


def _replay_one(capsule: Capsule, args: argparse.Namespace, round_number: int) -> dict[str, Any]:
    scenario = _apply_scenario_overrides(
        scenario_from_capsule(capsule, round_number=round_number), args
    )
    rpc = _rpc_from_args(args, rpc_hint=scenario.rpc_hint)
    return ReplayEngine(rpc).run(scenario).to_dict()


def cmd_replay(args: argparse.Namespace) -> int:
    capsule = Capsule.load(args.capsule)
    if args.all_rounds:
        results: list[dict[str, Any]] = []
        for round_number in capsule.trace_rounds():
            try:
                results.append(
                    {
                        "round": round_number,
                        "ok": True,
                        "result": _replay_one(capsule, args, round_number),
                    }
                )
            except Exception as exc:
                results.append({"round": round_number, "ok": False, "error": str(exc)})
        payload = {
            "schema_version": 1,
            "tx_id": capsule.manifest.tx_id,
            "rounds": results,
            "successful": sum(1 for item in results if item["ok"]),
            "attempted": len(results),
        }
        if args.json:
            _print_json(payload)
        else:
            print(f"source tx : {capsule.manifest.tx_id}")
            for item in results:
                if item["ok"]:
                    sig = item["result"]["signature"]
                    print(
                        f"round {item['round']}: PASS status={sig.get('status_code')} "
                        f"disagreement={sig.get('nondet_disagreement_call')}"
                    )
                else:
                    print(f"round {item['round']}: FAIL {item['error']}")
            print(f"replayed: {payload['successful']}/{payload['attempted']}")
        return 0 if results and all(item["ok"] for item in results) else 2

    result = _replay_one(capsule, args, args.round)
    if args.json:
        _print_json(result)
    else:
        scenario = result["scenario"]
        sig = result["signature"]
        print(f"source tx      : {scenario['source_tx_id']}")
        print(f"target         : {scenario['to_address']}")
        print(f"round          : {scenario['round_number']}")
        print(f"leader outputs : {len(scenario['leader_results'])}")
        print(f"status         : {sig.get('status_code')} {sig.get('status_message')}")
        print(f"disagreement   : {sig.get('nondet_disagreement_call')}")
    return 0


def cmd_fork(args: argparse.Namespace) -> int:
    capsule = Capsule.load(args.capsule)
    scenario = _apply_scenario_overrides(scenario_from_capsule(capsule, round_number=args.round), args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(pretty_json(scenario.to_dict()), encoding="utf-8")
    print(output)
    return 0


def cmd_run_scenario(args: argparse.Namespace) -> int:
    scenario = _load_scenario(args.scenario)
    rpc = _rpc_from_args(args, rpc_hint=scenario.rpc_hint)
    result = ReplayEngine(rpc).run(scenario).to_dict()
    if args.json:
        _print_json(result)
    else:
        _print_json(result["signature"])
    return 0


def cmd_minimize(args: argparse.Namespace) -> int:
    scenario = _load_scenario(args.scenario)
    rpc = _rpc_from_args(args, rpc_hint=scenario.rpc_hint)
    best, trials = ReplayEngine(rpc).minimize_leader_prefix(scenario)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(pretty_json(best.to_dict()), encoding="utf-8")
    trials_path = Path(args.trials_output) if args.trials_output else output.with_suffix(".trials.json")
    trials_path.write_text(pretty_json(trials), encoding="utf-8")
    print(f"leader results: {len(scenario.leader_results)} -> {len(best.leader_results)}")
    print(f"scenario: {output}")
    print(f"trials  : {trials_path}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    result = diff_capsules(Capsule.load(args.left), Capsule.load(args.right), full=args.full)
    if args.json:
        _print_json(result)
    else:
        print(f"left : {result['left']}")
        print(f"right: {result['right']}")
        print(f"analysis changes: {len(result['analysis'])}")
        print(f"changed files   : {len(result['changed_file_digests'])}")
        for change in result["analysis"][:30]:
            print(f"  {change['kind']:7} {change['path']}")
    return 0


def cmd_export_test(args: argparse.Namespace) -> int:
    output = export_pytest(args.capsule, args.output)
    print(output)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = int(args.handler(args))
    except (GenReplayError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"genreplay: error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
