import sys


def main() -> None:
    data = sys.stdin.read()
    lines = data.splitlines()
    if not lines:
        return

    word_counts = [len(line.split()) for line in lines]

    max_count = max(word_counts)
    best_line = word_counts.index(max_count) + 1
    average = sum(word_counts) / len(word_counts)

    print(f"{best_line} {average:.2f}")


if __name__ == "__main__":
    main()
