import base64

SAMPLES = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"hello world"]


def main() -> None:
    for data in SAMPLES:
        encoded = base64.b64encode(data)
        print(encoded)
        print(encoded.decode())
        print(base64.b64decode(encoded) == data)
        print(base64.standard_b64encode(data) == encoded)
        print(base64.urlsafe_b64encode(data))
        print(base64.b64decode(encoded.decode()) == data)
        print(base64.standard_b64decode(encoded) == data)
    print(base64.b64decode(b"") == b"")
    print(base64.b64decode("") == b"")
    binary = b"\xfb\xff\x00\x01"
    print(base64.urlsafe_b64encode(binary))
    print(base64.urlsafe_b64decode(base64.urlsafe_b64encode(binary)) == binary)
    text = "hello"
    print(base64.b64decode(base64.b64encode(text.encode()).decode()).decode())


main()
