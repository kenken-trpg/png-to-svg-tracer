from pathlib import Path
import errno
import resource
import shutil
import subprocess
from xml.etree import ElementTree as ET
import sys

from limits import MAX_OUTPUT, MAX_PIXELS, MAX_UPLOAD, TRACE_EDGE


def cap(kind, maximum):
    soft, hard = resource.getrlimit(kind)
    limit = min(value for value in (soft, hard, maximum) if value != resource.RLIM_INFINITY)
    resource.setrlimit(kind, (limit, limit))


def smooth_palette(image, destination, preset):
    from io import BytesIO

    labels = image.quantize(colors=32)
    width, height = labels.size
    paths_size = 0
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.Element("{http://www.w3.org/2000/svg}svg", width=str(width), height=str(height),
                      viewBox=f"0 0 {width} {height}")
    for _, index in sorted(labels.getcolors(), reverse=True):
        rgb = labels.getpalette("RGBA")[4 * index:4 * index + 4]
        r, g, b, alpha = rgb
        if not alpha:
            continue
        mask = labels.copy()
        mask.putpalette([v for i in range(256) for v in ([0] * 3 if i == index else [255] * 3)])
        mask.info.clear()
        bitmap = BytesIO()
        mask.convert("1").save(bitmap, format="PPM")
        layer = destination.with_name("layer.svg")
        tolerance = {"シンプル": "0.5", "標準": "0.2", "高精細": "0.1"}[preset]
        subprocess.run(["potrace", "--svg", "--turdsize", "0", "--opttolerance", tolerance,
                        "--output", str(layer), "-"], input=bitmap.getvalue(), check=True)
        paths_size += layer.stat().st_size
        if paths_size >= MAX_OUTPUT:
            raise OSError(errno.EFBIG, "SVG output limit")
        group = ET.parse(layer).getroot().find("{http://www.w3.org/2000/svg}g")
        if group is not None:
            group.set("fill", f"#{r:02x}{g:02x}{b:02x}")
            group.set("fill-opacity", f"{alpha / 255:.3f}")
            root.append(group)
    ET.ElementTree(root).write(destination, encoding="utf-8")


def palette_svg(image, destination, binary, preset):
    from itertools import groupby
    from PIL import Image

    image.thumbnail((512, 512))
    colors = {"シンプル": 8, "標準": 16, "高精細": 32}[preset]
    if binary:
        white = Image.new("RGBA", image.size, "white")
        white.alpha_composite(image)
        image = white.convert("L").point(lambda value: 255 if value >= 128 else 0).convert("RGBA")
    else:
        image = image.quantize(colors=colors).convert("RGBA")
    if shutil.which("potrace"):
        smooth_palette(image, destination, preset)
        return
    width, height = image.size
    # Join adjacent pixels of equal color into horizontal strips.
    with destination.open("w", encoding="utf-8") as svg:
        svg.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
        for y in range(height):
            row = image.crop((0, y, width, y + 1))
            x = 0
            for (r, g, b, a), pixels in groupby(row.get_flattened_data()):
                length = sum(1 for _ in pixels)
                if a:
                    svg.write(f'<path fill="#{r:02x}{g:02x}{b:02x}" fill-opacity="{a / 255:.3f}" d="M{x} {y}h{length}v1h-{length}z"/>')
                x += length
            if svg.tell() >= MAX_OUTPUT:
                raise OSError(errno.EFBIG, "SVG output limit")
        svg.write("</svg>")


def convert(directory, color, preset, engine="vtracer"):
    from PIL import Image

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
    if engine == "palette":
        palette_svg(rgba, directory / "output.svg", binary, preset)
        return 0
    import vtracer
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
