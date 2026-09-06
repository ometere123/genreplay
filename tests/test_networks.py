from genreplay.networks import PRESETS, get_network, identify_network, resolve_rpc


def test_expected_networks_exist():
    assert {"studionet", "studio-dev", "localnet", "testnet-bradbury", "testnet-asimov"} <= set(PRESETS)


def test_current_studionet_identity():
    preset = get_network("studionet")
    assert preset.chain_id == 61999
    assert preset.rpc_url == "https://studio.genlayer.com/api"


def test_current_studio_dev_identity():
    preset = get_network("studio-dev")
    assert preset.chain_id == 61997
    assert preset.rpc_url == "https://studio-dev.genlayer.com/api"


def test_aliases():
    assert get_network("bradbury").name == "testnet-bradbury"
    assert get_network("studio_dev").name == "studio-dev"


def test_unknown_network_rejected():
    try:
        get_network("mars")
    except ValueError as exc:
        assert "unknown network" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_identify_by_rpc():
    assert identify_network("https://studio.genlayer.com/api", 999) == "studionet"


def test_identify_unique_chain():
    assert identify_network("https://custom", 61997) == "studio-dev"


def test_shared_chain_not_guessed():
    assert identify_network("https://custom", 4221) is None


def test_resolve_custom_rpc_wins():
    url, preset = resolve_rpc(network="studionet", rpc_url="https://example.test/rpc")
    assert url == "https://example.test/rpc"
    assert preset is not None and preset.name == "studionet"
