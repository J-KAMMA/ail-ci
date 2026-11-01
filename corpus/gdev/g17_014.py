# task: Compose a list of unary functions into a single pipeline with functools.reduce and apply it to sample numbers.
from __future__ import annotations

import functools
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def compose(*funcs: Callable[[T], T]) -> Callable[[T], T]:
    """Compose unary functions left-to-right into a single pipeline."""
    def compose2(f: Callable[[T], T], g: Callable[[T], T]) -> Callable[[T], T]:
        return lambda x: g(f(x))
    return functools.reduce(compose2, funcs, lambda x: x)


def add(n: int) -> Callable[[int], int]:
    return lambda x: x + n


def multiply(n: int) -> Callable[[int], int]:
    return lambda x: x * n


def square(x: int) -> int:
    return x * x


def negate(x: int) -> int:
    return -x


def clamp(lo: int, hi: int) -> Callable[[int], int]:
    return lambda x: max(lo, min(hi, x))


def apply_to_all(pipeline: Callable[[int], int], values: Iterable[int]) -> list[int]:
    return [pipeline(v) for v in values]


def main() -> None:
    pipeline = compose(
        add(3),
        multiply(2),
        square,
        negate,
        clamp(-100, 50),
    )

    samples = [-7, -2, 0, 1, 4, 9, 12, 25]

    print("Pipeline: add(3) -> multiply(2) -> square -> negate -> clamp(-100, 50)")
    for value in samples:
        print(f"f({value:>3}) = {pipeline(value)}")

    results = apply_to_all(pipeline, samples)
    print("All results:", results)
    print("Sum of results:", sum(results))


if __name__ == "__main__":
    main()
