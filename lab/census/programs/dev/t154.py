import sys


def main() -> None:
    data = sys.stdin.read().split()
    numbers: list[int] = [int(tok) for tok in data]

    if not numbers:
        print(0)
        return

    current_min: int = numbers[0]
    current_max: int = numbers[0]
    max_changes: int = 0

    print(f"({current_min}, {current_max})")

    for value in numbers[1:]:
        if value < current_min:
            current_min = value
        if value > current_max:
            current_max = value
            max_changes += 1
        print(f"({current_min}, {current_max})")

    print(max_changes)


if __name__ == "__main__":
    main()
