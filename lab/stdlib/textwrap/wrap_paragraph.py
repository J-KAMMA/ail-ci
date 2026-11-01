import textwrap

ARTICLE = (
    "The quick brown fox jumps over the lazy dog while the morning sun "
    "climbs above the quiet hills. A small stream runs beside the path, "
    "and the wind carries the smell of pine needles through the valley."
)


def main() -> None:
    for width in (20, 40, 70):
        print(f"--- width {width} ---")
        print(textwrap.fill(ARTICLE, width))
    words = textwrap.wrap(ARTICLE, width=30)
    print(len(words))
    for line in words:
        print(f"[{line}]")
    print(textwrap.wrap("", 10))
    print(textwrap.fill("", 10))
    print(textwrap.wrap("   ", 10))


main()
