import sys


def longest_common_substring(a: str, b: str) -> tuple[str, int]:
    best_len = 0
    best_end = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > best_len:
                    best_len = curr[j]
                    best_end = i
        prev = curr
    return a[best_end - best_len:best_end], best_len


def main() -> None:
    data = sys.stdin.read().split("\n")
    a = data[0].strip() if len(data) > 0 else ""
    b = data[1].strip() if len(data) > 1 else ""
    sub, length = longest_common_substring(a, b)
    print(sub)
    print(length)


if __name__ == "__main__":
    main()
