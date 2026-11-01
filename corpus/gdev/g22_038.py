# task: Define permission flags with enum.IntFlag, combine a set of them with bitwise OR, and print membership tests.
import enum
from typing import Iterable


class Permission(enum.IntFlag):
    NONE = 0
    READ = enum.auto()
    WRITE = enum.auto()
    EXECUTE = enum.auto()
    DELETE = enum.auto()
    ADMIN = enum.auto()


ALL_PERMISSION_NAMES: tuple[str, ...] = (
    "READ",
    "WRITE",
    "EXECUTE",
    "DELETE",
    "ADMIN",
)


def combine(perms: Iterable[Permission]) -> Permission:
    result = Permission.NONE
    for perm in perms:
        result |= perm
    return result


def describe(flags: Permission) -> str:
    names = [name for name in ALL_PERMISSION_NAMES
             if Permission[name] in flags]
    return "|".join(names) if names else "NONE"


def main() -> None:
    user_perms = combine([Permission.READ, Permission.WRITE])
    admin_perms = combine([Permission.READ, Permission.WRITE,
                           Permission.DELETE, Permission.ADMIN])

    print(f"user_perms  = {describe(user_perms)} (value={int(user_perms)})")
    print(f"admin_perms = {describe(admin_perms)} (value={int(admin_perms)})")
    print()

    print("Membership tests for user_perms:")
    for name in ALL_PERMISSION_NAMES:
        perm = Permission[name]
        print(f"  {name:<8} in user_perms: {perm in user_perms}")
    print()

    print("Membership tests for admin_perms:")
    for name in ALL_PERMISSION_NAMES:
        perm = Permission[name]
        print(f"  {name:<8} in admin_perms: {perm in admin_perms}")
    print()

    combined_all = user_perms | admin_perms
    print(f"Union of both: {describe(combined_all)} (value={int(combined_all)})")

    common = user_perms & admin_perms
    print(f"Intersection:  {describe(common)} (value={int(common)})")

    removed = admin_perms & ~Permission.DELETE
    print(f"Admin without DELETE: {describe(removed)} (value={int(removed)})")

    has_all_user = (user_perms & combine([Permission.READ, Permission.WRITE])
                    == combine([Permission.READ, Permission.WRITE]))
    print(f"user_perms contains READ|WRITE: {has_all_user}")

    print(f"EXECUTE alone in admin_perms: {Permission.EXECUTE in admin_perms}")
    print(f"Empty set contains NONE: {Permission.NONE in user_perms}")


if __name__ == "__main__":
    main()
