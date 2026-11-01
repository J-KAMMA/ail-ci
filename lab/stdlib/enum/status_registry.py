from enum import Enum


class Status(Enum):
    NEW = 1
    ACTIVE = 2
    CLOSED = 3

    @classmethod
    def from_code(cls, code):
        for status in cls:
            if status.value == code:
                return status
        raise ValueError(code)

    @classmethod
    def all_names(cls):
        return [status.name for status in cls]


def main():
    print(Status.from_code(2))
    print(Status.all_names())
    try:
        Status.from_code(9)
    except ValueError as error:
        print("ValueError", error)


main()
