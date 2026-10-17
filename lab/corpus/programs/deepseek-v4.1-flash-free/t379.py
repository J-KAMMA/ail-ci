import sys
from functools import cmp_to_key


def largest_concatenation(numbers: list[int]) -> str:
    def compare(a: int, b: int) -> int:
        ab = str(a) + str(b)
        ba = str(b) + str(a)
        if ab > ba:
            return -1
        if ab < ba:
            return 1
        return 0

    ordered = sorted(numbers, key=cmp_to_key(compare))
    return "".join(str(x) for x in ordered)


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(x) for x in data[1:1 + n]]

    lexicographic = sorted(numbers, key=lambda x: str(x))
    print(" ".join(str(x) for x in lexicographic))
    print(largest_concatenation(numbers))


if __name__ == "__main__":
    main()
