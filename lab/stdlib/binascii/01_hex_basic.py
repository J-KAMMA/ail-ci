import binascii


def main() -> None:
    samples = [b"", b"\x00", b"\x00\xff", b"abc", bytes(range(16))]
    for data in samples:
        print(binascii.hexlify(data).decode())
        print(binascii.b2a_hex(data).decode())
    print(binascii.hexlify(bytearray(b"ab")).decode())
    print(binascii.hexlify(b"\xb9\x01\xef").decode())
    print(binascii.b2a_hex(b"\xb9\x01\xef").decode())
    print(len(binascii.hexlify(b"plain ascii")))


main()
