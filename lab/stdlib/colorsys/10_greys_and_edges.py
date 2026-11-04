import colorsys


def report(label: str, r: float, g: float, b: float) -> None:
    print(label, "hls", repr(colorsys.rgb_to_hls(r, g, b)))
    print(label, "hsv", repr(colorsys.rgb_to_hsv(r, g, b)))
    print(label, "yiq", repr(colorsys.rgb_to_yiq(r, g, b)))


def main() -> None:
    report("black", 0.0, 0.0, 0.0)
    report("dark grey", 0.25, 0.25, 0.25)
    report("mid grey", 0.5, 0.5, 0.5)
    report("light grey", 0.75, 0.75, 0.75)
    report("white", 1.0, 1.0, 1.0)
    report("below zero", -0.25, -0.1, -0.5)
    report("above one", 1.25, 1.1, 1.5)
    report("mixed range", -0.2, 0.5, 1.2)
    print("clamped yiq", repr(colorsys.yiq_to_rgb(0.5, 0.9, 0.9)))
    print("clamped yiq low", repr(colorsys.yiq_to_rgb(0.5, -0.9, -0.9)))


main()
