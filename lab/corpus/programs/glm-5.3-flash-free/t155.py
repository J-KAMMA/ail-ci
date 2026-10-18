from collections import Counter


def main() -> None:
    numbers = [int(token) for token in input().split()]
    counts = Counter(numbers)
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{value} {count}")


if __name__ == "__main__":
    main()
