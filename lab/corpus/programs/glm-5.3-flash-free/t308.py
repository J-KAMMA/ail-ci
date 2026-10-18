def longest_common_substring(s1: str, s2: str) -> tuple[str, int]:
    """Return the longest common substring occurring first in s1 and its length."""
    best_len = 0
    best_start = 0
    prev = [0] * (len(s2) + 1)

    for i, c1 in enumerate(s1, 1):
        cur = [0] * (len(s2) + 1)
        for j, c2 in enumerate(s2, 1):
            if c1 == c2:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best_len:
                    best_len = cur[j]
                    best_start = i - cur[j]
        prev = cur

    return s1[best_start:best_start + best_len], best_len


def main() -> None:
    s1 = input().strip()
    s2 = input().strip()
    substring, length = longest_common_substring(s1, s2)
    print(substring)
    print(length)


if __name__ == "__main__":
    main()
