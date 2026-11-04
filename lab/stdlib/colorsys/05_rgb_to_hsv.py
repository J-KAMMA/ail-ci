import colorsys


def show(name: str, r: float, g: float, b: float) -> None:
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    print(name, h, s, v)
    print(name, repr(h), repr(s), repr(v))


def main() -> None:
    show("red", 1.0, 0.0, 0.0)
    show("green", 0.0, 1.0, 0.0)
    show("blue", 0.0, 0.0, 1.0)
    show("white", 1.0, 1.0, 1.0)
    show("black", 0.0, 0.0, 0.0)
    show("grey", 0.5, 0.5, 0.5)
    show("mixed", 0.2, 0.4, 0.7)
    h, s, v = colorsys.rgb_to_hsv(255, 0, 0)
    print("ints", h, s, v)
    print("ints", repr(h), repr(s), repr(v))


main()
