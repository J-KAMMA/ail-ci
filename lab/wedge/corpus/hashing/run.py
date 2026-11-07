"""Driver for hashing: checksum a fixed payload many times."""
import hashing as m

SIZE = 200000
TEXT = "the quick brown fox jumps over the lazy dog 0123456789" * 2000


def main() -> None:
    data = bytes((i * 37 + 11) % 256 for i in range(SIZE))
    a = 0
    b = 0
    c = 0
    d = 0
    e = 0
    f = 0
    g = 0
    for _r in range(24):
        a += m.fnv1a(data) & 0xFFFF
        b += m.fnv1a_64(data) & 0xFFFF
        c += m.adler32_simple(data) & 0xFFFF
        d += m.sum_bytes(data)
        e += m.xor_fold(data)
        f += m.djb2(TEXT) & 0xFFFF
        g += m.sum_bytes(data) & 0xFF
    print("bytes", len(data))
    print("fnv1a", a)
    print("fnv1a_64", b)
    print("adler", c)
    print("sum", d)
    print("xor", e)
    print("djb2", f)
    print("low", g)
    print("crc", m.crc32_table_free(data[:20000]))


main()
