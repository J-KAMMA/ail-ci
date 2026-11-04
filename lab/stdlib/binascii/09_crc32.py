import binascii

ZLIB_WHOLE = 3456913684


def main() -> None:
    data = b"the quick brown fox jumps over the lazy dog"
    whole = binascii.crc32(data)
    running = 0
    pos = 0
    while pos < len(data):
        end = pos + 7
        if end > len(data):
            end = len(data)
        running = binascii.crc32(data[pos:end], running)
        pos = end
    print(whole)
    print(running)
    print(whole == ZLIB_WHOLE)
    print(binascii.crc32(b""))
    print(binascii.crc32(b"abc", 12345))
    print(binascii.crc32(b"abc", 0))
    print(binascii.crc32(b"abc", 7))


main()
