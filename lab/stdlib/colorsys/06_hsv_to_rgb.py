import colorsys


def show(name: str, h: float, s: float, v: float) -> None:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    print(name, r, g, b)
    print(name, repr(r), repr(g), repr(b))


def main() -> None:
    show("red", 0.0, 1.0, 1.0)
    show("green", 1.0 / 3.0, 1.0, 1.0)
    show("blue", 2.0 / 3.0, 1.0, 1.0)
    show("hue one", 1.0, 1.0, 1.0)
    show("hue below", 0.999999, 1.0, 1.0)
    show("negative hue", -0.25, 1.0, 1.0)
    show("grey", 0.0, 0.0, 0.5)
    show("mixed", 0.55, 0.4, 0.8)


main()
