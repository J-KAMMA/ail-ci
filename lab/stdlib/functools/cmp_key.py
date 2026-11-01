"""Multi-key sorting with functools.cmp_to_key."""
from functools import cmp_to_key


def compare(a, b):
    if a[1] != b[1]:
        return -1 if a[1] < b[1] else 1
    if a[2] != b[2]:
        return -1 if a[2] > b[2] else 1
    if a[0] != b[0]:
        return -1 if a[0] < b[0] else 1
    return 0


def main() -> None:
    people = [
        ("zoe", 30, 2),
        ("amy", 30, 1),
        ("bob", 25, 3),
        ("dan", 30, 1),
        ("eve", 25, 3),
    ]
    ascending = sorted(people, key=cmp_to_key(compare))
    print(ascending)
    people.sort(key=cmp_to_key(compare), reverse=True)
    print(people)
    print(sorted([], key=cmp_to_key(compare)))
    print(sorted([("solo", 1, 1)], key=cmp_to_key(compare)))
    pairs = [(3, "c"), (1, "a"), (2, "b")]
    print(sorted(pairs, key=cmp_to_key(lambda a, b: a[0] - b[0])))
    print(min(people, key=cmp_to_key(compare)))
    print(max(people, key=cmp_to_key(compare)))


main()
