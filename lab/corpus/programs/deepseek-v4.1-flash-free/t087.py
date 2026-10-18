import sys


def compress(s: str) -> str:
    parts: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        j = i
        while j < n and s[j] == s[i]:
            j += 1
        run = j - i
        parts.append(s[i])
        if run > 1:
            parts.append(str(run))
        i = j
    return "".join(parts)


def decompress(s: str) -> str:
    chars: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        i += 1
        digits: list[str] = []
        while i < n and s[i].isdigit():
            digits.append(s[i])
            i += 1
        count = int("".join(digits)) if digits else 1
        chars.append(ch * count)
    return "".join(chars)


def main() -> None:
    for line in sys.stdin:
        s = line.strip()
        if not s:
            continue
        compressed = compress(s)
        print(compressed)
        if decompress(compressed) == s:
            print("ok")


if __name__ == "__main__":
    main()
