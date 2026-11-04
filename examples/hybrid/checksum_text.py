"""A rolling hash over a str parameter.

This is the example the current prototype refuses: `ord` is a call, and the hybrid body gate
keeps a call that can raise or have a side effect in CPython.  The program still runs, and its
output still equals CPython; it just gets no extension for `rolling_hash`.
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
