import colorsys


def show(name: str, h: float, l: float, s: float) -> None:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    print(name, r, g, b)
    print(name, repr(r), repr(g), repr(b))


def main() -> None:
    show("red", 0.0, 0.5, 1.0)
    show("green", 1.0 / 3.0, 0.5, 1.0)
    show("blue", 2.0 / 3.0, 0.5, 1.0)
    show("hue one", 1.0, 0.5, 1.0)
    show("hue below", 0.999999, 0.5, 1.0)
    show("grey", 0.0, 0.5, 0.0)
    show("white", 0.0, 1.0, 0.0)
    show("dark", 0.25, 0.2, 0.6)


main()
