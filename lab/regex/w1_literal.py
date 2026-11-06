"""w1: count literal occurrences of "error" in the ASCII log and "café" in the mixed text."""
import re
import sys
import zlib


def main() -> int:
    ascii_data = open(sys.argv[1], encoding="utf-8").read()
    mixed_data = open(sys.argv[2], encoding="utf-8").read()

    n_ascii = 0
    h_ascii = 0
    for m in re.finditer(r"error", ascii_data):
        n_ascii += 1
        h_ascii = zlib.crc32(m.group(0).encode(), h_ascii)

    n_mixed = 0
    h_mixed = 0
    for m in re.finditer(r"café", mixed_data):
        n_mixed += 1
        h_mixed = zlib.crc32(m.group(0).encode(), h_mixed)

    print("w1 count=%d hash=%d count_mixed=%d hash_mixed=%d"
          % (n_ascii, h_ascii, n_mixed, h_mixed))
    return 0


main()
