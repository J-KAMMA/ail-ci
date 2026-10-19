import sys


def is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def count_left_aligned_differences(a: str, b: str) -> int:
    longest = max(len(a), len(b))
    count = 0
    for i in range(longest):
        if i >= len(a) or i >= len(b) or a[i] != b[i]:
            count += 1
    return count


def main() -> None:
    lines = sys.stdin.read().split("\n")
    first = lines[0].rstrip("\r") if len(lines) > 0 else ""
    second = lines[1].rstrip("\r") if len(lines) > 1 else ""

    sub = is_subsequence(second, first)
    diff = count_left_aligned_differences(first, second)

    print(f"{'YES' if sub else 'NO'} {diff}")


if __name__ == "__main__":
    main()
