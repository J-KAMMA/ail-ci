import textwrap

WORDS = [
    "supercalifragilisticexpialidocious",
    "antidisestablishmentarianism",
    "short",
]


def main() -> None:
    for word in WORDS:
        print(textwrap.wrap(word, width=10))
        print(textwrap.wrap(word, width=10, break_long_words=False))
    phrase = "one two three-four five"
    print(textwrap.wrap(phrase, width=9, break_on_hyphens=False))
    print(textwrap.wrap(phrase, width=9, break_long_words=False,
                        break_on_hyphens=False))
    print(textwrap.fill("antidisestablishmentarianism", 12,
                        break_long_words=False))
    print(textwrap.wrap("well-known goof-ball", 6, break_on_hyphens=False))


main()
