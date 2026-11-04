import colorsys


def main() -> None:
    state = 12345
    sr = 0.0
    sg = 0.0
    sb = 0.0
    i = 0
    while i < 1000000:
        state = (state * 1103515245 + 12345) % 2147483648
        r = (state % 16777216) / 16777216.0
        state = (state * 1103515245 + 12345) % 2147483648
        g = (state % 16777216) / 16777216.0
        state = (state * 1103515245 + 12345) % 2147483648
        b = (state % 16777216) / 16777216.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        sr = sr + rr
        sg = sg + gg
        sb = sb + bb
        i = i + 1
    print(repr((sr, sg, sb)))


main()
