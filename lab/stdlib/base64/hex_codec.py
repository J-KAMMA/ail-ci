import base64


def main() -> None:
    for n in [0, 1, 2, 3, 15, 16, 17]:
        data = bytes(range(n))
        encoded = base64.b16encode(data)
        print(encoded)
        print(base64.b16decode(encoded) == data)
        print(base64.b16decode(encoded.lower(), casefold=True) == data)
    data = bytes(range(256))
    encoded = base64.b16encode(data)
    print(encoded)
    print(base64.b16decode(encoded) == data)
    print(base64.b16encode(b"hello\x00\xff"))
    print(base64.b16decode(b"68656C6C6F"))
    print(base64.b16decode(b"68656c6c6f", casefold=True))
    try:
        base64.b16decode(b"abc")
    except ValueError as exc:
        print("odd", str(exc))
    try:
        base64.b16decode(b"zz")
    except ValueError as exc:
        print("digit", str(exc))
    try:
        base64.b16decode(b"68656c6c6f")
    except ValueError as exc:
        print("case", str(exc))


main()
