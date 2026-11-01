from enum import Enum, unique


class ErrorCode(Enum):
    OK = 0
    NOT_FOUND = 404
    MISSING = ALSO_MISSING = 404
    DENIED = 403


@unique
class Severity(Enum):
    LOW = 1
    HIGH = 2


def describe(code):
    if code is ErrorCode.OK:
        return "ok"
    return code.name.lower()


def main():
    print([code.name for code in ErrorCode])
    print(list(ErrorCode.__members__))
    print(ErrorCode.MISSING is ErrorCode.NOT_FOUND, ErrorCode.ALSO_MISSING.name)
    print(ErrorCode(404), ErrorCode["ALSO_MISSING"], ErrorCode.MISSING.value)
    print(404 in ErrorCode, ErrorCode.MISSING in ErrorCode, 500 in ErrorCode)
    for raw in [0, 403, 404, 500]:
        try:
            code = ErrorCode(raw)
            print(raw, code, describe(code))
        except ValueError as error:
            print(raw, "ValueError", error)
    try:
        ErrorCode["NOPE"]
    except KeyError as error:
        print("KeyError", error)
    print(len(ErrorCode), len(ErrorCode.__members__), len(list(ErrorCode)))
    print([level.name for level in Severity])


main()
