import sys


def main() -> None:
    words = sys.stdin.readline().split()
    mid = len(words) // 2
    first, second = words[:mid], words[mid:]

    for a, b in zip(first, second):
        if a < b:
            print("a<b")
        elif a == b:
            print("a=b")
        else:
            print("a>b")


if __name__ == "__main__":
    main()
