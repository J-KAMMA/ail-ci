import sys


def main() -> None:
    line: str = sys.stdin.readline().rstrip("\r\n")
    size: int = 7
    chunks: list[str] = [line[i:i + size] for i in range(0, len(line), size)]
    print("|".join(chunks))
    print(line[::-1])


if __name__ == "__main__":
    main()
