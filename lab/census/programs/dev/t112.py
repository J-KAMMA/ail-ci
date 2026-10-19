import sys


def collapse_runs(text: str) -> str:
    """Remove consecutive duplicate characters, keeping the first of each run."""
    result: list[str] = []
    for ch in text:
        if not result or result[-1] != ch:
            result.append(ch)
    return "".join(result)


def main() -> None:
    line: str = sys.stdin.readline().rstrip("\r\n")
    reduced: str = collapse_runs(line)
    print(reduced)
    print(len(line), len(reduced))


if __name__ == "__main__":
    main()
