
__all__ = (
    "TapTracksError",
    "MissingDependency"
)

class TapTracksError(Exception):
    pass

class MissingDependency(TapTracksError):
    pass