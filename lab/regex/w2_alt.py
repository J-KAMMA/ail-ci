"""w2: case-insensitive word alternation error|warn|fatal over the ASCII log."""
import re
import sys
import zlib


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    n = 0
    h = 0
    for m in re.finditer(r"error|warn|fatal", data, re.I):
        n += 1
        h = zlib.crc32(m.group(0).encode(), h)

    print("w2 count=%d hash=%d" % (n, h))
    return 0


main()
