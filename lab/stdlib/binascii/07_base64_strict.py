import binascii


def main() -> None:
    good = [b"YWJj", b"YWJjZA==", b"", b"====", b"YWJj====", b"YW=="]
    for data in good:
        try:
            print("ok", binascii.a2b_base64(data, strict_mode=True).hex())
        except binascii.Error as exc:
            print("err", str(exc))
    bad = [b"YWJj\n", b" Y W J j ", b"YWJj!!!", b"=YWJj", b"YW=Jj",
           b"YWJjZA==YWJj", b"YWJjZA==="]
    for data in bad:
        try:
            print("ok", binascii.a2b_base64(data, strict_mode=True).hex())
        except binascii.Error as exc:
            print("err", str(exc))
    print(binascii.a2b_base64(b"YWJjZA==", strict_mode=False).decode())


main()
