"""Area calculations with functools.singledispatch over several shapes."""
from functools import singledispatch


@singledispatch
def area(shape):
    return "unknown"


@area.register
def _(shape: int) -> str:
    return f"square {shape * shape}"


@area.register
def _(shape: list) -> str:
    return f"rectangle {shape[0] * shape[1]}"


@area.register(str)
def _(shape):
    return f"text {len(shape)}"


def main() -> None:
    print(area(5))
    print(area([3, 4]))
    print(area("hello"))
    print(area(2.5))
    print(area((1, 2)))
    print(area.dispatch(int).__name__)
    print(area.dispatch(list).__name__)
    print(area.dispatch(str).__name__)
    print(sorted(cls.__name__ for cls in area.registry))


main()
