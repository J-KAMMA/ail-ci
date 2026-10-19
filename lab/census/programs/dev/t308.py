import sys


def main() -> None:
    data = sys.stdin.read().split("\n")
    s1 = data[0].strip() if len(data) > 0 else ""
    s2 = data[1].strip() if len(data) > 1 else ""

    n = len(s1)
    m = len(s2)

    prev: list[int] = [0] * (m + 1)
    best = 0
    best_end = 0  # end index (exclusive) in s1 of the best substring

    for i in range(1, n + 1):
        cur: list[int] = [0] * (m + 1)
        c = s1[i - 1]
        for j in range(1, m + 1):
            if c == s2[j - 1]:
                v = prev[j - 1] + 1
                cur[j] = v
                # Strict comparison keeps the earliest-ending (hence earliest-starting
                # for equal length) occurrence in the first string.
                if v > best:
                    best = v
                    best_end = i
        prev = cur

    result = s1[best_end - best:best_end]
    print(result)
    print(best)


if __name__ == "__main__":
    main()
