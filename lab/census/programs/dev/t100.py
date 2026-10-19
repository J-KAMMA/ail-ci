import sys


def main() -> None:
    lines: list[str] = sys.stdin.read().splitlines()

    if not lines:
        print(0)
        print(f"{0.0:.2f}")
        return

    counts: list[int] = [len(line.split()) for line in lines]

    best_index = 0
    for i, count in enumerate(counts):
        if count > counts[best_index]:
            best_index = i

    average = sum(counts) / len(counts)

    print(best_index + 1)
    print(f"{average:.2f}")


if __name__ == "__main__":
    main()
