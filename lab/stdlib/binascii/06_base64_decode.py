import binascii


def main() -> None:
    print(binascii.a2b_base64(b"YWJj").decode())
    print(binascii.a2b_base64(b"YWJjZA==").decode())
    print(binascii.a2b_base64(b" Y W J j \n").decode())
    print(binascii.a2b_base64(b"YWJj!!!").decode())
    print(binascii.a2b_base64(b"YWJjZA===").decode())
    print(binascii.a2b_base64(b"=YWJj").decode())
    print(binascii.a2b_base64(b"YW=Jj").decode())
    print(binascii.a2b_base64("YWJj").decode())
    print(binascii.a2b_base64(b"").decode())
    encoded = binascii.b2a_base64(bytes(range(120)), newline=False)
    print(binascii.a2b_base64(encoded).hex())
    print(binascii.a2b_base64(b"YWJj\nYWJj\n").decode())


main()
