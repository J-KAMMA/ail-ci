import zlib_gen_ffi


def read_u64(b: bytearray) -> int:
    v = 0
    for i in range(8):
        v = v | (b[i] << (8 * i))
    return v


def write_u64(b: bytearray, v: int) -> None:
    for i in range(8):
        b[i] = (v >> (8 * i)) & 255


def round_trip(data: bytes) -> None:
    bound = zlib_gen_ffi.compressBound(len(data))
    packed = bytearray(bound)
    packed_len = bytearray(8)
    write_u64(packed_len, bound)
    packed_rc = zlib_gen_ffi.compress2(packed, packed_len, data, 6)
    used = read_u64(packed_len)
    back = bytearray(len(data))
    back_len = bytearray(8)
    write_u64(back_len, len(data))
    back_rc = zlib_gen_ffi.uncompress(back, back_len, bytes(packed[0:used]))
    print("bound", bound, "rc", packed_rc, back_rc, "ok", read_u64(back_len) == len(data) and bytes(back) == data)


def main():
    # the major version only: the patch level differs between runners
    print("zlib", zlib_gen_ffi.zlibVersion().split(".")[0])
    checksums(b"")
    checksums(b"hello, zlib")
    checksums(b"the quick brown fox jumps over the lazy dog, twice: the quick brown fox jumps over the lazy dog")


def checksums(data: bytes) -> None:
    print("checksums", len(data), zlib_gen_ffi.crc32(0, data), zlib_gen_ffi.adler32(1, data))
    round_trip(data)


main()
