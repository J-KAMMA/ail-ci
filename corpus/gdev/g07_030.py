# task: Write a script that builds a list of run-length encoded tuples from a hardcoded list and prints the encoding.
from typing import List, Tuple, TypeVar

T = TypeVar("T")

DATA: List[str] = list("aaabccddddde") + list("xxxxyyz") + list("QQqqq")


def run_length_encode(items: List[T]) -> List[Tuple[T, int]]:
    """Return a list of (value, count) tuples for consecutive runs."""
    encoded: List[Tuple[T, int]] = []
    for item in items:
        if encoded and encoded[-1][0] == item:
            value, count = encoded[-1]
            encoded[-1] = (value, count + 1)
        else:
            encoded.append((item, 1))
    return encoded


def decode(encoded: List[Tuple[T, int]]) -> List[T]:
    """Expand (value, count) tuples back into the original sequence."""
    result: List[T] = []
    for value, count in encoded:
        result.extend([value] * count)
    return result


def main() -> None:
    encoding = run_length_encode(DATA)
    print("Input length:", len(DATA))
    print("Encoding:")
    for value, count in encoding:
        print(f"  ({value!r}, {count})")
    print("Runs:", len(encoding))
    print("Compact:", "".join(f"{v}{c}" for v, c in encoding))
    assert decode(encoding) == DATA, "round-trip failed"
    print("Round-trip check: OK")


if __name__ == "__main__":
    main()
