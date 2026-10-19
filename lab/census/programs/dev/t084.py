import sys


def is_palindrome_ignore_case(s: str) -> bool:
    folded = s.casefold()
    return folded == folded[::-1]


def main() -> None:
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    strings = tokens[1:1 + n]

    count = 0
    for s in strings:
        if is_palindrome_ignore_case(s):
            print("yes")
            count += 1
        else:
            print("no")
    print(count)


if __name__ == "__main__":
    main()
