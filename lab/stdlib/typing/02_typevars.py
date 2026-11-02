from typing import Iterable, List, Sequence, TypeVar

T = TypeVar("T")


def first(items: Sequence[T]) -> T:
    return items[0]


def last(items: Sequence[T]) -> T:
    return items[-1]


def count_matching(items: Iterable[str], prefix: str) -> int:
    n = 0
    for item in items:
        if item.startswith(prefix):
            n += 1
    return n


def repeat(value: T, n: int) -> List[T]:
    out: List[T] = []
    for _ in range(n):
        out.append(value)
    return out


def main() -> None:
    print(first([3, 4, 5]))
    print(last([3, 4, 5]))
    print(first(["a", "b"]))
    print(count_matching(["alpha", "beta", "apple"], "a"))
    print(count_matching([], "x"))
    print(repeat("ab", 3))
    print(repeat(7, 2))


main()
