from pathlib import Path
import errno
import resource
import sys

from limits import MAX_OUTPUT, MAX_PIXELS, MAX_UPLOAD, TRACE_EDGE


def cap(kind, maximum):
    soft, hard = resource.getrlimit(kind)
    limit = min(value for value in (soft, hard, maximum) if value != resource.RLIM_INFINITY)
    resource.setrlimit(kind, (limit, limit))


def convert(directory, color, preset):
    from PIL import Image
    import vtracer

    source = directory / "input.png"
    if source.stat().st_size > MAX_UPLOAD:
        return 2
    try:
        with Image.open(source, formats=["PNG"]) as image:
            if image.width * image.height > MAX_PIXELS:
                return 2
            image.thumbnail((TRACE_EDGE, TRACE_EDGE))
            rgba = image.convert("RGBA")
            rgba.info.clear()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return 3
    preview = directory / "preview.png"
    rgba.save(preview)
    binary = color == "白黒"
    if binary:
        white = Image.new("RGBA", rgba.size, "white")
        white.alpha_composite(rgba)
        mask = white.convert("L").point(lambda value: 255 if value >= 128 else 0)
        mask.save(source)
    precision, speckle = {"シンプル": (4, 8), "標準": (6, 4), "高精細": (8, 1)}[preset]
    svg = directory / "output.svg"
    try:
        vtracer.convert_image_to_svg_py(str(source if binary else preview), str(svg),
                                        colormode="binary" if binary else "color",
                                        color_precision=precision, filter_speckle=speckle)
    finally:
        if svg.exists() and svg.stat().st_size >= MAX_OUTPUT:
            raise OSError(errno.EFBIG, "SVG output limit")
    return 0


if __name__ == "__main__":
    cap(resource.RLIMIT_FSIZE, MAX_OUTPUT + 64 * 1024)
    if sys.platform.startswith("linux"):
        cap(resource.RLIMIT_AS, 448 * 1024**2)
    try:
        sys.exit(convert(Path(sys.argv[1]), *sys.argv[2:]))
    except OSError as error:
        if error.errno == errno.EFBIG:
            sys.exit(4)
        raise
