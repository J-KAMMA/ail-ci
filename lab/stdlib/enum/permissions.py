from enum import Flag, auto


class Perm(Flag):
    NONE = 0
    READ = auto()
    WRITE = auto()
    EXEC = auto()
    MODIFY = READ | WRITE


def describe(perm):
    parts = [member.name for member in perm]
    if not parts:
        return "none"
    return "+".join(parts)


def main():
    perm = Perm.READ | Perm.WRITE
    print(perm, repr(perm), perm.value, describe(perm))
    print(Perm.READ in perm, Perm.EXEC in perm, Perm.MODIFY in perm, Perm.NONE in perm)
    print(perm & Perm.WRITE, perm ^ Perm.READ, ~Perm.EXEC, Perm(5))
    print(Perm.MODIFY is (Perm.READ | Perm.WRITE))
    print(list(Perm), len(Perm), [member.value for member in Perm])
    for mask in (0, 1, 3, 7):
        flags = Perm(mask)
        print(mask, flags, describe(flags), flags.value)
    try:
        Perm(8)
    except ValueError as error:
        print("ValueError", error)
    print(Perm.NONE, bool(Perm.NONE), bool(Perm.READ))
    print(Perm.WRITE in (Perm.READ | Perm.WRITE | Perm.EXEC))


main()
