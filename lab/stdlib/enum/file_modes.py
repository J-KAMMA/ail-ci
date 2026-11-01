from enum import StrEnum, auto


class Mode(StrEnum):
    READ = "r"
    WRITE = "w"
    APPEND = auto()
    BINARY = auto()


def label(mode):
    return mode.name.title() + " (" + mode.upper() + ")"


def main():
    for mode in Mode:
        print(mode.name, str(mode), repr(mode), mode.value, label(mode))
    print(Mode.READ == "r", Mode("w"), Mode["APPEND"])
    print(Mode.BINARY.startswith("b"), Mode.APPEND.endswith("d"))
    print("|".join([m.value for m in Mode]))
    print(Mode.WRITE < Mode.READ, sorted(Mode, key=lambda m: m.value))
    aliases = {"r": Mode.READ, "w": Mode.WRITE}
    print(aliases["r"] is Mode.READ, aliases.get("a"))
    try:
        Mode("x")
    except ValueError as error:
        print("ValueError", error)


main()
