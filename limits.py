MAX_UPLOAD = 10 * 1024**2
MAX_PIXELS = 16_000_000
TRACE_EDGE = 1024
MAX_OUTPUT = 4 * 1024**2
TIMEOUT = 30


def palette_edge(preset):
    return 768 if preset == "高精細" else 512
