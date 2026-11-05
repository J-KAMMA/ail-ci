# expect: normalize=typed join_words=typed main=typed
def normalize(s: str) -> str:
    return s.strip()


def join_words(a: str, b: str) -> str:
    return a + "-" + b


def main() -> None:
    print(join_words(normalize("  hi  "), "there"))


main()
