import sys


def main() -> None:
    data = sys.stdin.read().splitlines()
    n = int(data[0].strip())
    words = [line.strip() for line in data[1 : n + 1]]
    for word in words:
        rev = word[::-1]
        print(f"{rev} {rev == word}")
    print("-".join(words))


if __name__ == "__main__":
    main()
