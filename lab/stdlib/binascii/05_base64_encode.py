import binascii


def main() -> None:
    for n in [0, 1, 2, 3, 4, 5, 6, 7]:
        data = bytes(range(n))
        print(binascii.b2a_base64(data).decode().rstrip("\n"))
        print(binascii.b2a_base64(data, newline=False).decode())
    print(binascii.b2a_base64(b"x" * 57, newline=False).decode())
    print(binascii.b2a_base64(b"x" * 58, newline=False).decode())
    print(len(binascii.b2a_base64(b"abc")))
    print(len(binascii.b2a_base64(b"abc", newline=False)))


main()
