import colorsys


def hex_color(r: float, g: float, b: float) -> str:
    ri = int(round(r * 255))
    gi = int(round(g * 255))
    bi = int(round(b * 255))
    return "#%02x%02x%02x" % (ri, gi, bi)


def main() -> None:
    hues = [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875]
    for hue in hues:
        r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
        print(hue, hex_color(r, g, b), repr(r), repr(g), repr(b))
    for value in [0.0, 0.5, 1.0]:
        r, g, b = colorsys.hls_to_rgb(0.5, value, 1.0)
        print("light", value, hex_color(r, g, b), repr(r), repr(g), repr(b))


main()
