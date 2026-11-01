import base64

def main() -> None:
    samples = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", bytes(range(100))]
    for data in samples:
        encoded = base64.b85encode(data)
        print(encoded)
        print(base64.b85decode(encoded) == data)
        ascii_encoded = base64.a85encode(data)
        print(ascii_encoded)
        print(base64.a85decode(ascii_encoded) == data)
    print(base64.a85encode(b"hello", adobe=True))
    print(base64.a85encode(b"hello", wrapcol=10))
    print(base64.b85encode(b"hello", pad=True))
    print(base64.b85decode(b"Xk~0{Zv"))
    print(base64.a85decode(b"87cURD]i,\"Ebo80"))


main()
