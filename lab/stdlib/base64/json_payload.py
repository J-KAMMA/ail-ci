import base64

PAYLOADS = [
    '{"name":"alice","email":"alice@example.com"}',
    '{"text":"caf\\u00e9 na\\u00efve"}',
    '{"items":[1,2,3],"ok":true}',
    "",
]


def encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def decode(token: str) -> str:
    return base64.b64decode(token).decode()


def main() -> None:
    for text in PAYLOADS:
        token = encode(text)
        print(token)
        print(decode(token))
        print(decode(token) == text)
    multibyte = "caf\u00e9 \u2014 na\u00efve"
    token = base64.b64encode(multibyte.encode()).decode()
    print(token)
    print(base64.b64decode(token).decode())
    print(base64.b64decode(token.encode()))
    try:
        base64.b64decode("caf\u00e9")
    except ValueError as exc:
        print("nonascii", str(exc))


main()
