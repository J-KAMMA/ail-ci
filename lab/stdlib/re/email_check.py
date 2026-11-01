import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HOST = re.compile(r"@([A-Za-z0-9.-]+)$")


def check(addr: str) -> int:
    if not addr:
        return 0
    if EMAIL.fullmatch(addr) is None:
        return 1
    m = HOST.search(addr)
    if m is None:
        return 2
    host = m.group(1).lower()
    if host.endswith("example.com") or host.endswith("example.org"):
        return 10
    return 3


def main() -> int:
    for addr in ["a@example.com", "", "bad", "x@example.org", "x@other.test"]:
        print(addr, check(addr))
    print(EMAIL.pattern)
    print(re.escape("a.b@c+d"))
    for part in ["1", "x", " 7 "]:
        try:
            print(int(part))
        except ValueError:
            print("not a number", repr(part))
    return 0


main()
