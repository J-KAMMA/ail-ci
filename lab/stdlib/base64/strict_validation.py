import base64

def show(token: bytes, validate: bool) -> None:
    try:
        print(validate, base64.b64decode(token, validate=validate))
    except ValueError as exc:
        print(validate, str(exc))


def main() -> None:
    cases = [
        b"aGVsbG8=",
        b"aGVs bG8=",
        b"aGVsbG8",
        b"aGVsbG8==",
        b"aGVsbG8$=",
        b"=aGVsbG8",
        b"aGVsbG8=extra",
    ]
    for token in cases:
        show(token, False)
        show(token, True)
    for token in [b"aGVsbG8=", b"aGVsbG8-", b"aGVsbG8_"]:
        try:
            print("alt", base64.b64decode(token, altchars=b"-_", validate=True))
        except ValueError as exc:
            print("alt", str(exc))
    try:
        base64.b64decode("aGVsbG8=", validate=True)
    except ValueError as exc:
        print("str", str(exc))
    print(base64.b64decode(b"aGVsbG8=", validate=True))
    try:
        print(base64.b64decode(b"aGVsbG8", validate=False))
    except ValueError as exc:
        print("padding", str(exc))


main()
