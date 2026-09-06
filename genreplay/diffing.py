from __future__ import annotations

from typing import Any

from .capsule import Capsule


def json_diff(left: Any, right: Any, *, path: str = "$") -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    if type(left) is not type(right):
        return [{"path": path, "kind": "type", "before": left, "after": right}]
    if isinstance(left, dict):
        keys = sorted(set(left) | set(right))
        for key in keys:
            child = f"{path}.{key}"
            if key not in left:
                changes.append({"path": child, "kind": "added", "after": right[key]})
            elif key not in right:
                changes.append({"path": child, "kind": "removed", "before": left[key]})
            else:
                changes.extend(json_diff(left[key], right[key], path=child))
        return changes
    if isinstance(left, list):
        max_len = max(len(left), len(right))
        for index in range(max_len):
            child = f"{path}[{index}]"
            if index >= len(left):
                changes.append({"path": child, "kind": "added", "after": right[index]})
            elif index >= len(right):
                changes.append({"path": child, "kind": "removed", "before": left[index]})
            else:
                changes.extend(json_diff(left[index], right[index], path=child))
        return changes
    if left != right:
        changes.append({"path": path, "kind": "changed", "before": left, "after": right})
    return changes


def diff_capsules(left: Capsule, right: Capsule, *, full: bool = False) -> dict[str, Any]:
    left_summary = left.read_json("analysis/summary.json") if left.has("analysis/summary.json") else {}
    right_summary = right.read_json("analysis/summary.json") if right.has("analysis/summary.json") else {}
    result: dict[str, Any] = {
        "left": left.manifest.tx_id,
        "right": right.manifest.tx_id,
        "manifest": json_diff(left.manifest.to_dict(), right.manifest.to_dict()),
        "analysis": json_diff(left_summary, right_summary),
        "files_only_left": sorted(set(left.files) - set(right.files)),
        "files_only_right": sorted(set(right.files) - set(left.files)),
        "changed_file_digests": [],
    }
    shared = sorted(set(left.files) & set(right.files))
    for name in shared:
        lmeta = left.manifest.files.get(name, {})
        rmeta = right.manifest.files.get(name, {})
        if lmeta.get("sha256") != rmeta.get("sha256"):
            result["changed_file_digests"].append(name)
    if full:
        detail: dict[str, Any] = {}
        for name in result["changed_file_digests"]:
            if name.endswith(".json"):
                try:
                    detail[name] = json_diff(left.read_json(name), right.read_json(name))
                except Exception:
                    pass
        result["detail"] = detail
    return result
