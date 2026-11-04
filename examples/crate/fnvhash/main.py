from fnvhash_ffi import fnv1a64
from bigbuffer import one_megabyte


def main():
    print(fnv1a64(b""))
    print(fnv1a64(b"a"))
    print(one_megabyte())
    print(fnv1a64(b"hello"))
    print(fnv1a64(b"the quick brown fox"))


main()
