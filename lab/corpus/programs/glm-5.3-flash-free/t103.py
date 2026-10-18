import sys
from typing import List


def main() -> None:
    words: List[str] = sys.stdin.read().split()
    if not words:
        return

    comma_joined: str = ", ".join(words)
    if len(words) == 1:
        and_joined: str = words[0]
    else:
        and_joined = ", ".join(words[:-1]) + " and " + words[-1]

    width: int = max(len(word) for word in words)
    column: str = "\n".join(word.rjust(width) for word in words)

    print(comma_joined)
    print(and_joined)
    print(column)


if __name__ == "__main__":
    main()
