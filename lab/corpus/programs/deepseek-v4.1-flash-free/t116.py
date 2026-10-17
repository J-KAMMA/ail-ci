import sys
import textwrap


def main() -> None:
    text = sys.stdin.readline().rstrip("\n")
    print(textwrap.fill(text, width=30))
    print(textwrap.shorten(text, width=40))


if __name__ == "__main__":
    main()
