import colorsys


def show(name: str, y: float, i: float, q: float) -> None:
    r, g, b = colorsys.yiq_to_rgb(y, i, q)
    print(name, r, g, b)
    print(name, repr(r), repr(g), repr(b))


def main() -> None:
    show("grey", 0.5, 0.0, 0.0)
    show("white", 1.0, 0.0, 0.0)
    show("black", 0.0, 0.0, 0.0)
    show("redish", 0.3, 0.5, 0.2)
    show("low", 0.2, -0.4, -0.3)
    show("high", 0.8, 0.4, 0.3)
    show("mixed", 0.45, 0.1, -0.2)


main()
