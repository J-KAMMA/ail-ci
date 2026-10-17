import sys


def main() -> None:
    line = sys.stdin.readline().rstrip("\n")

    chunks = [line[i:i + 7] for i in range(0, len(line), 7)]
    print("|".join(chunks))
    print(line[::-1])


if __name__ == "__main__":
    main()
