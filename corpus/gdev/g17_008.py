# task: Use functools.cmp_to_key to sort a list of version strings such as '1.10.2' numerically.
from functools import cmp_to_key
from typing import List, Tuple


def parse_version(version: str) -> Tuple[int, ...]:
    """Split a dotted version string into a tuple of integers."""
    return tuple(int(part) for part in version.split("."))


def compare_versions(a: str, b: str) -> int:
    """Compare two version strings numerically.

    Returns a negative number if a < b, zero if equal, positive if a > b.
    Shorter versions are padded with zeros, so '1.2' equals '1.2.0'.
    """
    pa = parse_version(a)
    pb = parse_version(b)
    length = max(len(pa), len(pb))
    pa = pa + (0,) * (length - len(pa))
    pb = pb + (0,) * (length - len(pb))
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def sort_versions(versions: List[str]) -> List[str]:
    """Return a new list of version strings sorted numerically."""
    return sorted(versions, key=cmp_to_key(compare_versions))


def main() -> None:
    versions: List[str] = [
        "1.10.2",
        "1.2.0",
        "1.2",
        "1.10",
        "1.2.10",
        "2.0.0",
        "1.9.9",
        "10.0.1",
        "1.10.2.1",
        "0.9.11",
        "1.2.3",
        "1.02.3",
    ]

    sorted_versions = sort_versions(versions)
    print("Sorted versions:")
    for version in sorted_versions:
        print(f"  {version}")


if __name__ == "__main__":
    main()
