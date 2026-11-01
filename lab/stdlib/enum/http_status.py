from enum import IntEnum


class Status(IntEnum):
    OK = 200
    CREATED = 201
    MOVED = 301
    NOT_FOUND = 404
    SERVER_ERROR = 500


def category(code):
    if code < 300:
        return "success"
    if code < 400:
        return "redirect"
    if code < 500:
        return "client"
    return "server"


def parse(raw):
    return Status(int(raw))


def main():
    descriptions = {Status.OK: "ok", Status.NOT_FOUND: "missing"}
    for raw in ["200", "404", "500", "301", "201"]:
        code = parse(raw)
        print(code.name, int(code), category(code), code.value, f"{code:>3}")
    print(Status.OK == 200, Status.NOT_FOUND > 400)
    print(Status.OK + 1, 600 - Status.SERVER_ERROR)
    print(Status.OK ** 2, Status.CREATED ** 2)
    print(sorted(Status), max(Status), sum(Status))
    print(descriptions[Status.OK], Status.NOT_FOUND in descriptions)
    try:
        Status(418)
    except ValueError as error:
        print("ValueError", error)


main()
