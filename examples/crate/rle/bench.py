import sys

from rle_ffi import rle_encode


def main():
    data = open(sys.argv[1], "rb").read()
    out = bytearray(2 * len(data) + 2)
    print(len(data), rle_encode(data, out, len(out)))


main()
