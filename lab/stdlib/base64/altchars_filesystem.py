import base64


def encode(data: bytes) -> bytes:
    return base64.b64encode(data, altchars=b"-.")


def decode(token: bytes) -> bytes:
    return base64.b64decode(token, altchars=b"-.")


def main() -> None:
    for n in range(0, 12):
        data = bytes(range(n))
        token = encode(data)
        print(token)
        print(decode(token) == data)
        print(token == base64.urlsafe_b64encode(data).replace(b"_", b"."))
    data = bytes(range(256))
    alt = b"-_"
    token = base64.b64encode(data, alt)
    print(token)
    print(base64.b64decode(token, alt) == data)
    print(base64.b64decode(token, altchars=alt, validate=True) == data)
    print(base64.b64encode(b"", altchars=b"-_"))
    print(base64.b64encode(b"\xfb\xff", altchars=b"-_"))
    print(base64.b64decode(b"-_8=", altchars=b"-_"))


main()
