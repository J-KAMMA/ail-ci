# task: Write a generator that yields the Gray code sequence for 3 bits and print each value in binary form.
from collections.abc import Iterator


def gray_code(bits: int) -> Iterator[int]:
    """Yield the binary reflected Gray code sequence for the given number of bits."""
    for i in range(1 << bits):
        yield i ^ (i >> 1)


def main() -> None:
    bits = 3
    for value in gray_code(bits):
        print(format(value, f"0{bits}b"))


if __name__ == "__main__":
    main()
