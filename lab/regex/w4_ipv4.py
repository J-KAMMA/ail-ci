"""w4: IPv4 search with four groups; count valid addresses and hash each match."""
import re
import sys
import zlib


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    total = 0
    valid = 0
    h = 0
    for m in re.finditer(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b", data):
        a = int(m.group(1))
        b = int(m.group(2))
        c = int(m.group(3))
        d = int(m.group(4))
        total += 1
        if a <= 255 and b <= 255 and c <= 255 and d <= 255:
            valid += 1
        h = zlib.crc32(m.group(0).encode(), h)

    print("w4 total=%d valid=%d invalid=%d hash=%d" % (total, valid, total - valid, h))
    return 0


main()
