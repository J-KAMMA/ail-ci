import sys

from fnvhash_ffi import fnv1a64


def main():
    data = open(sys.argv[1], "rb").read()
    print(len(data), fnv1a64(data))


main()
