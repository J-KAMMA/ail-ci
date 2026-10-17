import sys


def is_rotation(a: str, b: str) -> bool:
    return len(a) == len(b) and b in a + a


def is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def main() -> None:
    data = sys.stdin.readline().split()
    a, b = data[0], data[1]

    rotation = is_rotation(a, b)
    subsequence = is_subsequence(a, b) or is_subsequence(b, a)
    common = "".join(sorted(set(a) & set(b)))

    print("Yes" if rotation else "No")
    print("Yes" if subsequence else "No")
    print(common)


if __name__ == "__main__":
    main()
