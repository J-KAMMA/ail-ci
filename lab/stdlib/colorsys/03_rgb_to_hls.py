import colorsys


def show(name: str, r: float, g: float, b: float) -> None:
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    print(name, h, l, s)
    print(name, repr(h), repr(l), repr(s))


def main() -> None:
    show("red", 1.0, 0.0, 0.0)
    show("green", 0.0, 1.0, 0.0)
    show("blue", 0.0, 0.0, 1.0)
    show("white", 1.0, 1.0, 1.0)
    show("black", 0.0, 0.0, 0.0)
    show("grey", 0.5, 0.5, 0.5)
    show("mixed", 0.2, 0.4, 0.7)
    show("dark", 0.1, 0.2, 0.3)


main()
