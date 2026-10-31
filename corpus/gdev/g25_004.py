# task: Implement a Flag enum for file permissions (READ, WRITE, EXECUTE), combine several flags, and print the resulting values and membership checks.
from enum import Flag, auto


class Permission(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()


def describe(perm: Permission) -> str:
    if perm == Permission(0):
        return "NONE"
    names: list[str] = [
        member.name
        for member in (Permission.READ, Permission.WRITE, Permission.EXECUTE)
        if member in perm
    ]
    return "|".join(names)


def main() -> None:
    read_only: Permission = Permission.READ
    read_write: Permission = Permission.READ | Permission.WRITE
    all_perms: Permission = Permission.READ | Permission.WRITE | Permission.EXECUTE
    none_perm: Permission = Permission(0)

    combos: list[tuple[str, Permission]] = [
        ("read_only", read_only),
        ("read_write", read_write),
        ("all_perms", all_perms),
        ("none_perm", none_perm),
    ]

    print("Combined flag values:")
    for label, perm in combos:
        print(f"  {label}: value={perm.value}, repr={perm!r}, str={describe(perm)}")

    print("Membership checks:")
    for label, perm in combos:
        for flag in (Permission.READ, Permission.WRITE, Permission.EXECUTE):
            print(f"  {label} has {flag.name}: {flag in perm}")

    print("Bitwise operations:")
    combined: Permission = read_write & ~Permission.WRITE
    print(f"  (READ|WRITE) & ~WRITE = {combined!r} value={combined.value}")
    toggled: Permission = all_perms ^ Permission.EXECUTE
    print(f"  ALL ^ EXECUTE = {toggled!r} value={toggled.value}")
    print(f"  READ in ALL: {Permission.READ in all_perms}")
    print(f"  Is read_write a subset of all? {(read_write & all_perms) == read_write}")


if __name__ == "__main__":
    main()
