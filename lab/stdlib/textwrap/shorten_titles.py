import textwrap

TITLES = [
    "A short title",
    "A considerably longer title that will not fit in the card",
    "Release notes for version 2.4 with migration advice",
    "  extra   spaces\tand\nnewlines  ",
]


def main() -> None:
    for title in TITLES:
        print(repr(textwrap.shorten(title, 24)))
    for width in (5, 8, 12):
        try:
            print(width, repr(textwrap.shorten(
                "one two three four five", width, placeholder="...")))
        except ValueError as exc:
            print(width, "ValueError", exc)
    try:
        textwrap.shorten("a b", 2)
    except ValueError as exc:
        print("tiny", "ValueError", exc)


main()
