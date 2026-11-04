"""Count lines, words and bytes on standard input, like wc without a file name."""

import sys


def main() -> None:
    data = sys.stdin.buffer.read()
    lines = data.count(b"\n")
    words = len(data.split())
    print("%7d %7d %7d" % (lines, words, len(data)))


main()
