import binascii


def main() -> None:
    for data in [b"YWJ", b"YWJjZA", b"Y", b"YWJjY", b"AAAAA", b"A", b"AA"]:
        try:
            binascii.a2b_base64(data)
        except binascii.Error as exc:
            print(str(exc))
    try:
        binascii.a2b_base64(b"Y")
    except ValueError as exc:
        print("as ValueError", str(exc))
    try:
        binascii.a2b_base64(b"YWJjZA=")
    except binascii.Error as exc:
        print("padding", str(exc))


main()
