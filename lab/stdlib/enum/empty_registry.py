from enum import Enum


class NoModes(Enum):
    pass


class Kind(Enum):
    FILE = 1
    DIRECTORY = 2
    SYMLINK = 1


def main():
    print(len(NoModes), list(NoModes), dict(NoModes.__members__))
    print(Kind.FILE in NoModes, 1 in NoModes)
    try:
        NoModes(1)
    except TypeError as error:
        print("TypeError", error)
    print(len(Kind), [kind.name for kind in Kind])
    print(list(Kind.__members__), len(Kind.__members__))
    print(Kind.SYMLINK is Kind.FILE, Kind(1).name)
    try:
        Kind["MISSING"]
    except KeyError as error:
        print("KeyError", error)
    selected = []
    for kind in Kind:
        if kind.value > 1:
            selected.append(kind.name)
    print(selected)


main()
