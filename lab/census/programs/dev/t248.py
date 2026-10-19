import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    r = int(data[0])
    c = int(data[1])
    values = list(map(int, data[2:2 + r * c]))
    matrix: list[list[int]] = [values[i * c:(i + 1) * c] for i in range(r)]

    palindrome_count = sum(1 for row in matrix if row == row[::-1])

    # Flip horizontally (reverse each row) and vertically (reverse row order).
    flipped: list[list[int]] = [row[::-1] for row in reversed(matrix)]

    print(palindrome_count)
    for row in flipped:
        print(" ".join(map(str, row)))


if __name__ == "__main__":
    main()
