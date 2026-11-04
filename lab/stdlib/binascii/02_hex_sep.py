import binascii


def main() -> None:
    data = b"abcdefg"
    for bps in [1, 2, 3, 0, -1, -2, -3, 5]:
        print(binascii.hexlify(data, b":", bps).decode())
    print(binascii.b2a_hex(b"\xb9\x01\xef", b"_", 2).decode())
    print(binascii.hexlify(b"abcd", ":").decode())
    print(binascii.hexlify(b"abc", b"|", 2).decode())
    try:
        binascii.hexlify(b"abcd", b"::")
    except ValueError as exc:
        print("sep", str(exc))


main()
