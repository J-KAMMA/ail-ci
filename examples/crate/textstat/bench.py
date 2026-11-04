import sys

from textstat_ffi import stats


def read_u64(data, start):
    value = 0
    for index in range(8):
        value = value | (data[start + index] << (8 * index))
    return value


def main():
    data = open(sys.argv[1], "rb").read()
    out = bytearray(24)
    stats(data, out)
    counts = bytes(out)
    print(len(data), read_u64(counts, 0), read_u64(counts, 8), read_u64(counts, 16))


main()
