"""GenReplay: consensus replay infrastructure for GenLayer."""

from .capsule import Capsule, CapsuleManifest
from .client import GenReplay
from .rpc import GenLayerRpcClient

__all__ = ["Capsule", "CapsuleManifest", "GenLayer", "GenLayerRpcClient", "GenReplay"]
__version__ = "0.2.0"

# Backwards-compatible alias for integrations that prefer the package noun.
GenLayer = GenReplay
