"""A rolling hash over a str parameter.

Until obs5 the hybrid refused this one: `ord` is a call that can raise.  `ord(ch)` of one
character of a str cannot, so `rolling_hash` is now accelerated; the output still equals
CPython.
"""
import sys


def rolling_hash(text: str) -> int:
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) % 1000000007
    return h


def main():
    size = 20000
    if len(sys.argv) > 1:
        size = int(sys.argv[1])
    text = "".join(chr(97 + (i % 26)) for i in range(size))
    print("length %d" % len(text))
    print("hash %d" % rolling_hash(text))


main()
