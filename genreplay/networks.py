from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NetworkPreset:
    name: str
    rpc_url: str
    chain_id: int
    explorer: str | None = None
    purpose: str = ""


PRESETS: dict[str, NetworkPreset] = {
    "studionet": NetworkPreset(
        "studionet",
        "https://studio.genlayer.com/api",
        61999,
        "https://explorer-studio.genlayer.com",
        "Hosted stable development network",
    ),
    "studio-dev": NetworkPreset(
        "studio-dev",
        "https://studio-dev.genlayer.com/api",
        61997,
        "https://explorer-studio-dev.genlayer.com",
        "Consensus release-candidate preview",
    ),
    "localnet": NetworkPreset(
        "localnet",
        "http://localhost:4000/api",
        61127,
        "http://localhost:8080",
        "Local Studio / GLSim development network",
    ),
    "testnet-bradbury": NetworkPreset(
        "testnet-bradbury",
        "https://rpc-bradbury.genlayer.com",
        4221,
        "https://explorer-bradbury.genlayer.com",
        "Production-like GenLayer testnet",
    ),
    "testnet-asimov": NetworkPreset(
        "testnet-asimov",
        "https://rpc-asimov.genlayer.com",
        4221,
        "https://explorer-asimov.genlayer.com",
        "Infrastructure and stress-testing network",
    ),
}

ALIASES = {
    "bradbury": "testnet-bradbury",
    "asimov": "testnet-asimov",
    "studio_dev": "studio-dev",
    "studio": "studionet",
}


def get_network(name: str) -> NetworkPreset:
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    try:
        return PRESETS[key]
    except KeyError as exc:
        choices = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown network {name!r}; choose one of: {choices}") from exc


def identify_network(rpc_url: str, chain_id: int | None = None) -> str | None:
    normalized = rpc_url.rstrip("/")
    for preset in PRESETS.values():
        if normalized == preset.rpc_url.rstrip("/"):
            return preset.name
    if chain_id is not None:
        matches = [p.name for p in PRESETS.values() if p.chain_id == chain_id]
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_rpc(*, network: str | None, rpc_url: str | None) -> tuple[str, NetworkPreset | None]:
    if rpc_url:
        preset = None
        if network:
            preset = get_network(network)
        return rpc_url, preset
    preset = get_network(network or "studionet")
    return preset.rpc_url, preset
