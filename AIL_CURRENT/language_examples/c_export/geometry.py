"""One AIL file, two readers: `python3 geometry.py` runs it on CPython, and

    ail build --lib geometry geometry.py -o outdir

turns the @export functions into outdir/libgeometry.so, outdir/libgeometry.a and outdir/geometry.h.
The tests call the library from C, ctypes and Rust and compare every result with this file on CPython.
"""
from dataclasses import dataclass
from ail_ffi import export

SCALE = 3


@dataclass
class Point:
    x: int
    y: float
    visible: bool


def helper_square(n: int) -> int:        # not exported: any AIL code may be used inside
    return n * n


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def scaled(x: float) -> float:
    return x * SCALE + 0.5


@export
def divide(a: int, b: int) -> int:       # b == 0 raises ZeroDivisionError: status + last_error, no crash
    return a // b


@export
def parse_digit(text: str) -> int:
    position = "0123456789".find(text)
    if len(text) != 1 or position < 0:
        raise ValueError("not a digit: " + text)
    return position


@export
def negate(flag: bool) -> bool:
    return not flag


@export
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def reverse_bytes(data: bytes) -> bytes:
    out = bytearray()
    i = len(data) - 1
    while i >= 0:
        out.append(data[i])
        i -= 1
    return bytes(out)


@export
def total(values: list[int]) -> int:
    t = 0
    for v in values:
        t += v
    return t


@export
def squares(values: list[int]) -> list[int]:
    out = []
    for v in values:
        out.append(helper_square(v))
    return out


@export
def mean(values: list[float]) -> float:
    t = 0.0
    for v in values:
        t += v
    return t / len(values)          # an empty list raises ZeroDivisionError


@export
def halves(values: list[float]) -> list[float]:
    out = []
    for v in values:
        out.append(v / 2.0)
    return out


@export
def weight(p: Point) -> float:
    if p.visible:
        return p.x * p.y
    return 0.0


@export
def first_item(values: list[int]) -> int:
    return values[0]                # an empty list raises IndexError


@export
def count_up(n: int) -> None:           # a void export: only the status comes back
    if n < 0:
        raise ValueError("n must not be negative")


if __name__ == "__main__":
    print(add(2, 3), divide(7, 2), shout("héllo"), squares([1, 2, 3]), weight(Point(2, 1.5, True)))
