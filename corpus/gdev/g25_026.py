# task: Define an IntFlag enum for user roles and compute the combined permissions for a fixed set of users, printing the results.
from enum import IntFlag, auto


class Role(IntFlag):
    NONE = 0
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    ADMIN = auto()
    AUDIT = auto()

    ALL = READ | WRITE | EXECUTE | ADMIN | AUDIT


USERS: dict[str, Role] = {
    "alice": Role.READ | Role.WRITE | Role.ADMIN,
    "bob": Role.READ,
    "carol": Role.READ | Role.EXECUTE | Role.AUDIT,
    "dave": Role.NONE,
    "erin": Role.ALL,
}


def combined_permissions(users: dict[str, Role], names: list[str]) -> Role:
    """Return the bitwise OR of the permissions held by the named users."""
    result = Role.NONE
    for name in names:
        result |= users[name]
    return result


def describe(perms: Role) -> str:
    """Return a stable, human-readable description of a permission set."""
    if perms == Role.NONE:
        return "NONE"
    members = [m.name for m in Role if m.name and m != Role.ALL and m in perms]
    return "|".join(sorted(members))


def main() -> None:
    for name in sorted(USERS):
        perms = USERS[name]
        print(f"{name:<6} value={int(perms):2d} roles={describe(perms)}")

    team_a = ["alice", "bob"]
    team_b = ["carol", "dave"]
    everyone = sorted(USERS)

    for label, names in (
        ("team_a", team_a),
        ("team_b", team_b),
        ("everyone", everyone),
    ):
        combined = combined_permissions(USERS, names)
        print(f"{label:<9} value={int(combined):2d} roles={describe(combined)}")

    has_admin = [n for n in everyone if Role.ADMIN in USERS[n]]
    print("admins:", ", ".join(has_admin))

    lacks_write = [n for n in everyone if Role.WRITE not in USERS[n]]
    print("without WRITE:", ", ".join(lacks_write))

    overlap = combined_permissions(USERS, ["alice", "carol"]) & combined_permissions(
        USERS, ["bob", "erin"]
    )
    print(f"overlap alice+carol vs bob+erin: {describe(overlap)}")


if __name__ == "__main__":
    main()
