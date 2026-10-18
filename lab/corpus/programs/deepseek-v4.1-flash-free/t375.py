import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1 : 1 + n]
    words.sort(key=len, reverse=True)
    sys.stdout.write("\n".join(words) + "\n")


if __name__ == "__main__":
    main()
