"""w7: re.split on \\s*,\\s*, one log line at a time."""
import re
import sys
import zlib


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    lines = 0
    fields = 0
    h = 0
    for line in data.split("\n"):
        if line == "":
            continue
        parts = re.split(r"\s*,\s*", line)
        lines += 1
        fields += len(parts)
        h = zlib.crc32("\x00".join(parts).encode(), h)

    print("w7 lines=%d fields=%d hash=%d" % (lines, fields, h))
    return 0


main()
