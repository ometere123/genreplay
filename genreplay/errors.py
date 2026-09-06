class GenReplayError(Exception):
    """Base error for user-actionable GenReplay failures."""


class RpcError(GenReplayError):
    """JSON-RPC transport or protocol error."""

    def __init__(self, message: str, *, code: int | None = None, data: object = None):
        super().__init__(message)
        self.code = code
        self.data = data


class CapsuleError(GenReplayError):
    """Invalid, corrupt, or unsupported replay capsule."""


class ReplayError(GenReplayError):
    """A replay could not be constructed or executed safely."""
