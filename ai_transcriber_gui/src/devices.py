"""Audio source helpers for the AI STT GUI."""

try:
    import soundcard as sc
except Exception:
    sc = None


DEFAULT_SOURCES = ["麥克風", "系統音"]


def get_available_sources() -> list:
    """Return the recording sources shown in the UI."""
    return DEFAULT_SOURCES.copy()


def normalize_source(source: str) -> str:
    """Map free-form source values to a supported recording source."""
    if source in DEFAULT_SOURCES:
        return source
    if source == "WASAPI Loopback":
        return "系統音"
    return "麥克風"
