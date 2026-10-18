import sys


def is_subsequence(s: str, t: str) -> bool:
    it = iter(s)
    return all(ch in it for ch in t)


def left_aligned_differences(s: str, t: str) -> int:
    return sum(1 for a, b in zip(s, t) if a != b)


def main() -> None:
    lines = sys.stdin.read().splitlines()
    first = lines[0].strip() if len(lines) > 0 else ""
    second = lines[1].strip() if len(lines) > 1 else ""

    print("True" if is_subsequence(first, second) else "False")
    print(left_aligned_differences(first, second))


if __name__ == "__main__":
    main()
