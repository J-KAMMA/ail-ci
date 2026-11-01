import base64


def wrap(data: bytes) -> bytes:
    return base64.encodebytes(data)


def unwrap(data: bytes) -> bytes:
    return base64.decodebytes(data)


def main() -> None:
    for n in [0, 1, 2, 3, 56, 57, 58, 76, 100, 200]:
        data = bytes(range(n))
        encoded = wrap(data)
        print(n, len(encoded), encoded.count(b"\n"))
        print(encoded)
        print(unwrap(encoded) == data)
    text = base64.encodebytes(b"hello world" * 30)
    print(text)
    print(base64.decodebytes(text))
    spaced = b"aGVs\n bG8=\n"
    print(base64.decodebytes(spaced))
    print(base64.encodebytes(b""))
    print(base64.decodebytes(b""))
    print(base64.decodebytes(base64.encodebytes(bytes(range(256)))) == bytes(range(256)))


main()
