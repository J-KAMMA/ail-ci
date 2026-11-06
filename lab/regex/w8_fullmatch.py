"""w8: fullmatch validation of one million short strings, a quarter of them non-ASCII."""
import re
import sys

EMAIL = re.compile(r"[a-z]+[0-9]+@example\.com")
IPV4 = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")
KEY = re.compile(r"[a-z_]+[0-9]+")
CAFE = re.compile(r"café[0-9]+")


def main() -> int:
    accepted = 0
    h = 0
    for i in range(1000000):
        kind = i % 4
        if kind == 0:
            if i % 11 == 0:
                s = "user%d@example.org" % i
            else:
                s = "user%d@example.com" % i
            ok = EMAIL.fullmatch(s) is not None
        elif kind == 1:
            a = i % 256
            b = (i * 7) % 256
            c = (i * 13) % 256
            d = (i * 29) % 256
            if i % 17 == 0:
                s = "999.%d.%d.%d" % (b, c, d)
            else:
                s = "%d.%d.%d.%d" % (a, b, c, d)
            ok = IPV4.fullmatch(s) is not None
        elif kind == 2:
            s = "key_%d" % i
            ok = KEY.fullmatch(s) is not None
        else:
            s = "café%d" % i
            ok = CAFE.fullmatch(s) is not None
        if ok:
            accepted += 1
            h = (h * 131 + i) % 1000000007

    print("w8 accepted=%d rejected=%d hash=%d" % (accepted, 1000000 - accepted, h))
    return 0


main()
