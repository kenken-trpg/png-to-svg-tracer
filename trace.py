import sys

import vtracer
from PIL import Image


def trace(source, destination, color, preset):
    precision, speckle = {"シンプル": (4, 8), "標準": (6, 4), "高精細": (8, 1)}[preset]
    binary = color == "白黒"
    if binary:
        with Image.open(source) as image:
            white = Image.new("RGBA", image.size, "white")
            white.alpha_composite(image.convert("RGBA"))
            mask = white.convert("L").point(lambda value: 255 if value >= 128 else 0)
        mask.save(source)
    vtracer.convert_image_to_svg_py(source, destination, colormode="binary" if binary else "color",
                                    color_precision=precision, filter_speckle=speckle)


if __name__ == "__main__":
    trace(*sys.argv[1:])
