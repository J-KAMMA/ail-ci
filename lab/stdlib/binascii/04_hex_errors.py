import binascii


def main() -> None:
    cases = [b"abc", b"61zz", b" 61", b"61 63", b"0g", b"7"]
    for data in cases:
        try:
            binascii.unhexlify(data)
        except binascii.Error as exc:
            print("Error", str(exc))
    try:
        binascii.a2b_hex(b"zz")
    except ValueError as exc:
        print("ValueError", str(exc))
    try:
        binascii.unhexlify(b"x1")
    except binascii.Error as exc:
        print("again", str(exc))


main()
