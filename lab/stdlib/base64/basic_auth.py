import base64

USERS = [("alice", "s3cret"), ("bob", ""), ("carol", "pass:word")]


def make_header(user: str, password: str) -> str:
    raw = (user + ":" + password).encode()
    return "Basic " + base64.b64encode(raw).decode()


def parse_header(header: str) -> str:
    token = header[6:]
    return base64.b64decode(token).decode()


def main() -> None:
    for user, password in USERS:
        header = make_header(user, password)
        print(header)
        print(parse_header(header))
    print(make_header("x", "y"))
    print(parse_header("Basic " + base64.standard_b64encode(b"a:b").decode()))
    try:
        base64.b64decode("not base64!")
    except ValueError as exc:
        print("invalid", str(exc))
    try:
        base64.b64decode("abcde")
    except ValueError as exc:
        print("length", str(exc))


main()
