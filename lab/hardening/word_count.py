import sys


def main() -> int:
    data = sys.stdin.buffer.read()
    newlines = 0
    words = 0
    in_word = False
    i = 0
    while i < len(data):
        c = data[i]
        if c == 10:
            newlines += 1
            if in_word:
                words += 1
                in_word = False
        elif c == 32 or c == 9 or c == 13:
            if in_word:
                words += 1
                in_word = False
        else:
            in_word = True
        i += 1
    if in_word:
        words += 1
    lines = newlines
    if len(data) > 0 and data[len(data) - 1] != 10:
        lines += 1
    print("bytes=%d lines=%d words=%d" % (len(data), lines, words))
    return 0


main()
