from ail_ffi import *

link("z")

@extern(header="zlib.h", symbol="crc32")
def c_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...

@extern(header="zlib.h", symbol="adler32")
def c_adler32(adler: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...

@extern(header="zlib.h", symbol="compressBound")
def c_compress_bound(n: c_ulong) -> c_ulong: ...

@extern(header="zlib.h", symbol="compress2")
def c_compress2(dest: bytearray, dest_len: ptr(c_ulong), src: bytes,
                n: length("src", c_ulong), level: c_int) -> c_int: ...

@extern(header="zlib.h", symbol="uncompress", check="nonzero", exc=ValueError)
def c_uncompress(dest: bytearray, dest_len: ptr(c_ulong), src: bytes,
                 n: length("src", c_ulong)) -> c_int: ...


def read_u64(b: bytearray) -> int:
    v = 0
    for i in range(8):
        v = v | (b[i] << (8 * i))
    return v


def write_u64(b: bytearray, v: int) -> None:
    for i in range(8):
        b[i] = (v >> (8 * i)) & 255


def checksums(data: bytes) -> None:
    print(c_crc32(0, data), c_adler32(1, data))


def main():
    checksums(b"")
    checksums(b"hello, zlib")
    checksums(b"abcdefghijklmnopqrstuvwxyz0123456789")
    data = b"the quick brown fox jumps over the lazy dog " * 8
    size = c_compress_bound(len(data))
    packed = bytearray(size)
    packed_len = bytearray(8)
    write_u64(packed_len, size)
    c_compress2(packed, packed_len, data, 6)
    used = read_u64(packed_len)
    back = bytearray(len(data))
    back_len = bytearray(8)
    write_u64(back_len, len(data))
    c_uncompress(back, back_len, bytes(packed[0:used]))
    if read_u64(back_len) == len(data) and bytes(back) == data:
        print("round trip ok")
    else:
        print("round trip failed")


main()
