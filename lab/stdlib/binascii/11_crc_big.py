import binascii


def main() -> None:
    data = b"abc"
    value = 1
    for _ in range(64):
        value = value * 2
    value = value + 5
    print(value)
    print(binascii.crc32(data, value))


main()
