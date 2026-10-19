import sys


def classify(word: str) -> str:
    """Return a 5-character T/F string for isalpha, isdigit, isupper, islower, istitle."""
    checks: tuple[bool, ...] = (
        word.isalpha(),
        word.isdigit(),
        word.isupper(),
        word.islower(),
        word.istitle(),
    )
    return "".join("T" if flag else "F" for flag in checks)


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    line: str = sys.stdin.read()
    for word in line.split():
        print(classify(word))


if __name__ == "__main__":
    main()
