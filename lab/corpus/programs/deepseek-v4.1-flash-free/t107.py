import sys


def main() -> None:
    words = sys.stdin.read().split()
    if len(words) < 3:
        print("short")
        return
    for i in range(len(words) - 2):
        print("+".join(words[i : i + 3]))


if __name__ == "__main__":
    main()
