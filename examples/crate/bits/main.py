from bits_ffi import bits_popcount, bits_rotl


def main():
    for value in (0, 1, 0b1011, 2147483648, 9223372036854775807):
        print(value, bits_popcount(value))
    print(bits_rotl(0x80000001, 1), bits_rotl(0x12345678, 8))
    print(bits_rotl(0x80000000, 64), bits_rotl(0xdeadbeef, 0))


main()
