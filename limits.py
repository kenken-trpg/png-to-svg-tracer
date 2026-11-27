import os

MAX_UPLOAD = 10 * 1024**2
MAX_PIXELS = 16_000_000
MAX_OUTPUT = 4 * 1024**2
TIMEOUT = 30


def trace_edge(preset):
    if preset == "高精細" and os.environ.get("PNG_TRACER_PROFILE") == "local":
        return 2048
    return 1024


def palette_edge(preset):
    return 768 if preset == "高精細" else 512
