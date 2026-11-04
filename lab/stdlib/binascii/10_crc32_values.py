import binascii


def main() -> None:
    data = b"abc"
    for value in [0, -1, 12345, 2 ** 31, 2 ** 32, 2 ** 32 + 7, 2 ** 63 - 1]:
        print(value, binascii.crc32(data, value))
    print(binascii.crc32(b"a" * 100, -5))
    print(binascii.crc32(b"", -1))
    print(binascii.crc32(b"\x00\x00\x00\x00", 1))


main()
