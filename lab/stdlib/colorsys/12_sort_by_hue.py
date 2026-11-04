import colorsys


def main() -> None:
    named = [("red", 1.0, 0.0, 0.0), ("green", 0.0, 1.0, 0.0),
             ("blue", 0.0, 0.0, 1.0), ("yellow", 1.0, 1.0, 0.0),
             ("cyan", 0.0, 1.0, 1.0), ("magenta", 1.0, 0.0, 1.0),
             ("orange", 1.0, 0.5, 0.0), ("grey", 0.5, 0.5, 0.5)]
    items = []
    for name, r, g, b in named:
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        items.append((h, name, s, v, r, g, b))
    items.sort()
    for h, name, s, v, r, g, b in items:
        print(name, repr(h), repr(s), repr(v), repr((r, g, b)))


main()
