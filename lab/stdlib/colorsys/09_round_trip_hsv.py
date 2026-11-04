import colorsys


def main() -> None:
    colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
              (1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (0.5, 0.5, 0.5),
              (0.2, 0.4, 0.7), (0.1, 0.2, 0.3), (0.9, 0.6, 0.1),
              (0.3, 0.3, 0.3), (0.8, 0.8, 0.8)]
    exact = 0
    total = 0
    for r, g, b in colors:
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        print((r, g, b), (h, s, v))
        print((r, g, b), repr((rr, gg, bb)))
        if rr == r and gg == g and bb == b:
            exact = exact + 1
        total = total + 1
    print("exact", exact, "of", total)


main()
