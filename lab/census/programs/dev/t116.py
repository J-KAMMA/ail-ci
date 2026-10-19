import textwrap


def main() -> None:
    text: str = input().strip()
    print(textwrap.fill(text, width=30))
    print(textwrap.shorten(text, width=40))


if __name__ == "__main__":
    main()
