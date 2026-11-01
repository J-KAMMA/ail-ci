import textwrap

URLS = [
    "https://example.com/a/very/long/path/that/keeps/going",
    "short/path",
    "state-of-the-art-toolkit",
]


def main() -> None:
    plain = textwrap.TextWrapper(width=30, break_long_words=False,
                                 break_on_hyphens=False)
    for url in URLS:
        print(plain.wrap(url))
    hyphen = textwrap.TextWrapper(width=18, break_on_hyphens=True)
    print(hyphen.wrap("state-of-the-art tools"))
    nohyphen = textwrap.TextWrapper(width=18, break_on_hyphens=False)
    print(nohyphen.wrap("state-of-the-art tools"))
    print(plain.fill("one two three"))


main()
