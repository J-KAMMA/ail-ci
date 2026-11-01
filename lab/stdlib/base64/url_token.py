import base64


def encode_token(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_token(token: str) -> bytes:
    padded = token + "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(padded)


def main() -> None:
    payloads = [b"", b"a", b"ab", b"abc", b'{"sub":"alice","exp":1700000000}', bytes(range(64))]
    for payload in payloads:
        token = encode_token(payload)
        print(token)
        print(decode_token(token) == payload)
        print(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)) == payload)
    print(encode_token(b"\xfb\xff\xfe"))
    print(base64.urlsafe_b64encode(b"hello+world/").decode())
    print(base64.urlsafe_b64decode("aGVsbG8rd29ybGQv"))
    print(base64.b64decode(base64.urlsafe_b64encode(b"a+b/c")))
    print(base64.urlsafe_b64encode(b"a+b/c"))


main()
