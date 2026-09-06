from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .errors import CapsuleError
from .util import canonical_json_bytes, sha256_bytes

CAPSULE_FORMAT = "genreplay-capsule"
CAPSULE_VERSION = 1


@dataclass(slots=True)
class CapsuleManifest:
    format: str
    version: int
    tool_version: str
    captured_at: str
    tx_id: str
    capture_level: str
    network: dict[str, Any]
    files: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CapsuleManifest:
        return cls(
            format=str(value["format"]),
            version=int(value["version"]),
            tool_version=str(value.get("tool_version", "unknown")),
            captured_at=str(value["captured_at"]),
            tx_id=str(value["tx_id"]),
            capture_level=str(value.get("capture_level", "protocol")),
            network=dict(value.get("network", {})),
            files=dict(value.get("files", {})),
        )


class Capsule:
    """Portable immutable-by-digest archive of a GenLayer consensus execution."""

    def __init__(self, manifest: CapsuleManifest, files: dict[str, bytes]):
        self.manifest = manifest
        self.files = files

    @classmethod
    def build(
        cls,
        *,
        tool_version: str,
        captured_at: str,
        tx_id: str,
        capture_level: str,
        network: dict[str, Any],
        files: dict[str, bytes],
    ) -> Capsule:
        metadata: dict[str, dict[str, Any]] = {}
        for name, data in sorted(files.items()):
            metadata[name] = {
                "sha256": sha256_bytes(data),
                "size": len(data),
            }
        manifest = CapsuleManifest(
            format=CAPSULE_FORMAT,
            version=CAPSULE_VERSION,
            tool_version=tool_version,
            captured_at=captured_at,
            tx_id=tx_id,
            capture_level=capture_level,
            network=network,
            files=metadata,
        )
        return cls(manifest, dict(files))

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            info = zipfile.ZipInfo("manifest.json")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, canonical_json_bytes(self.manifest.to_dict()))
            for name, data in sorted(self.files.items()):
                info = zipfile.ZipInfo(name)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
        temp.replace(destination)
        return destination

    @classmethod
    def load(cls, path: str | Path, *, verify: bool = True) -> Capsule:
        source = Path(path)
        try:
            with zipfile.ZipFile(source, "r") as zf:
                try:
                    manifest_raw = zf.read("manifest.json")
                except KeyError as exc:
                    raise CapsuleError("capsule is missing manifest.json") from exc
                try:
                    manifest_data = json.loads(manifest_raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise CapsuleError("capsule manifest is invalid JSON") from exc
                manifest = CapsuleManifest.from_dict(manifest_data)
                if manifest.format != CAPSULE_FORMAT:
                    raise CapsuleError(f"unsupported capsule format: {manifest.format!r}")
                if manifest.version != CAPSULE_VERSION:
                    raise CapsuleError(
                        f"unsupported capsule version {manifest.version}; expected {CAPSULE_VERSION}"
                    )
                files: dict[str, bytes] = {}
                for name in manifest.files:
                    try:
                        files[name] = zf.read(name)
                    except KeyError as exc:
                        raise CapsuleError(f"capsule is missing declared file {name}") from exc
        except zipfile.BadZipFile as exc:
            raise CapsuleError("not a valid .genreplay ZIP capsule") from exc
        capsule = cls(manifest, files)
        if verify:
            capsule.verify_integrity(raise_on_error=True)
        return capsule

    def verify_integrity(self, *, raise_on_error: bool = False) -> dict[str, Any]:
        errors: list[str] = []
        for name, meta in self.manifest.files.items():
            data = self.files.get(name)
            if data is None:
                errors.append(f"missing file: {name}")
                continue
            actual = sha256_bytes(data)
            expected = str(meta.get("sha256"))
            if actual != expected:
                errors.append(f"digest mismatch: {name}")
            expected_size = int(meta.get("size", -1))
            if len(data) != expected_size:
                errors.append(f"size mismatch: {name}")
        report = {"ok": not errors, "errors": errors, "file_count": len(self.manifest.files)}
        if errors and raise_on_error:
            raise CapsuleError("; ".join(errors))
        return report

    def has(self, name: str) -> bool:
        return name in self.files

    def read_bytes(self, name: str) -> bytes:
        try:
            return self.files[name]
        except KeyError as exc:
            raise CapsuleError(f"capsule does not contain {name}") from exc

    def read_json(self, name: str) -> Any:
        try:
            return json.loads(self.read_bytes(name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CapsuleError(f"capsule file {name} is not valid JSON") from exc

    def trace_rounds(self) -> list[int]:
        rounds: list[int] = []
        for name in self.files:
            if name.startswith("traces/round-") and name.endswith(".json"):
                try:
                    rounds.append(int(name.removeprefix("traces/round-").removesuffix(".json")))
                except ValueError:
                    continue
        return sorted(rounds)
