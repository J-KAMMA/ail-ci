import colorsys


def show(name: str, r: float, g: float, b: float) -> None:
    y, i, q = colorsys.rgb_to_yiq(r, g, b)
    print(name, y, i, q)
    print(name, repr(y), repr(i), repr(q))


def main() -> None:
    show("red", 1.0, 0.0, 0.0)
    show("green", 0.0, 1.0, 0.0)
    show("blue", 0.0, 0.0, 1.0)
    show("white", 1.0, 1.0, 1.0)
    show("black", 0.0, 0.0, 0.0)
    show("grey", 0.5, 0.5, 0.5)
    show("mixed", 0.2, 0.4, 0.7)


main()
