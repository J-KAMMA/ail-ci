"""w3: extract \\d+ runs and sum int(), then probe a 25-digit run.

The probe comes last on purpose.  CPython prints its exact value; AIL's int64 int() stops
loudly (exit 1, stderr names the overflow), so the digest line printed first is still
compared byte for byte.
"""
import re
import sys
import zlib


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    n = 0
    total = 0
    h = 0
    for m in re.finditer(r"\d+", data):
        v = int(m.group(0))
        n += 1
        total += v
        h = zlib.crc32(m.group(0).encode(), h)

    print("w3 count=%d sum=%d hash=%d" % (n, total, h))

    probe = "1234567890123456789012345"
    pm = re.fullmatch(r"\d+", probe)
    if pm is None:
        print("probe25=refused")
    else:
        print("probe25=%d" % int(pm.group(0)))
    return 0


main()
