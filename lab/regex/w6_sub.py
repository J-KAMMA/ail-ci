"""w6: re.sub with a group template, rewriting key=value as value:key."""
import re
import sys
import zlib


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    n = 0
    for m in re.finditer(r"(\w+)=(\d+)", data):
        n += 1
    out = re.sub(r"(\w+)=(\d+)", r"\2:\1", data)
    h = zlib.crc32(out.encode())

    print("w6 count=%d length=%d hash=%d" % (n, len(out), h))
    return 0


main()
