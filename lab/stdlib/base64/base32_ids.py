import base64


def main() -> None:
    for n in range(0, 12):
        data = bytes(range(n))
        encoded = base64.b32encode(data)
        print(encoded)
        print(base64.b32decode(encoded) == data)
        print(base64.b32decode(encoded.lower(), casefold=True) == data)
    data = b"hello world"
    token = base64.b32encode(data)
    print(token)
    print(base64.b32decode(token))
    print(base64.b32decode(b"MZXW6==="))
    print(base64.b32decode(b"MZXW6YTB"))
    print(base64.b32decode(b"MZXW6YTB".lower(), casefold=True))
    try:
        base64.b32decode(b"ABC")
    except ValueError as exc:
        print("padding", str(exc))
    try:
        base64.b32decode(b"MZXW6YT!")
    except ValueError as exc:
        print("digit", str(exc))
    try:
        base64.b32decode(b"mzxw6ytb")
    except ValueError as exc:
        print("case", str(exc))


main()
