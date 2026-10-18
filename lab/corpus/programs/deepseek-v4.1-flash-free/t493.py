import sys

WIDTH = 8
FILL = "_"


def main() -> None:
    line = sys.stdin.readline().rstrip("\n")
    for word in line.split():
        left = word.ljust(WIDTH, FILL)
        right = word.rjust(WIDTH, FILL)
        middle = word.center(WIDTH, FILL)
        print(f"ljust: {left} ({len(left)})")
        print(f"rjust: {right} ({len(right)})")
        print(f"center: {middle} ({len(middle)})")


if __name__ == "__main__":
    main()
