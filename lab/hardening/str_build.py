import sys


def main() -> int:
    parts: list[str] = []
    i = 0
    while i < 2000:
        parts.append("row-%d:" % i)
        if i % 3 == 0:
            parts.append("fizz")
        elif i % 5 == 0:
            parts.append("buzz")
        i += 1
    text = ""
    i = 0
    while i < len(parts):
        text += parts[i]
        text += ","
        i += 1
    h = 0
    i = 0
    while i < len(text):
        h = (h * 31 + ord(text[i])) % 1000000007
        i += 1
    print("parts=%d bytes=%d hash=%d" % (len(parts), len(text), h))
    return 0


main()
