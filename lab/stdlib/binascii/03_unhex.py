import binascii


def main() -> None:
    print(binascii.unhexlify(b"616263").decode())
    print(binascii.a2b_hex("616263").decode())
    print(binascii.unhexlify(b"616263DEF0").hex())
    print(binascii.unhexlify(b"616263def0").hex())
    print(binascii.unhexlify(b"").hex())
    print(binascii.unhexlify(bytearray(b"6162")).decode())
    print(binascii.a2b_hex("").hex())
    print(binascii.unhexlify("48656c6c6f").decode())
    print(binascii.unhexlify(b"00ff10").hex())


main()
