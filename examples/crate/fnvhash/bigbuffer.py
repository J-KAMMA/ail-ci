from fnvhash_ffi import fnv1a64


def one_megabyte():
    return fnv1a64(b"a" * (1024 * 1024))
