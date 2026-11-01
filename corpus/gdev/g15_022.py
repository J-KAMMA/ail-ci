# task: Run a list of invariant checks using assert inside try blocks, catch each AssertionError, and report which invariants failed.
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Invariant:
    name: str
    description: str
    check: Callable[[], None]


def check_sorted_after_sort() -> None:
    data = [5, 3, 9, 1, 7, 2]
    result = sorted(data)
    assert result == [1, 2, 3, 5, 7, 9], f"unexpected order: {result}"
    assert len(result) == len(data), "length changed during sort"


def check_sort_preserves_elements() -> None:
    data = [4, 4, 2, 8, 2]
    result = sorted(data)
    assert sorted(result) == sorted(data), "multiset of elements changed"
    assert result.count(4) == 2, "count of 4 is wrong"
    assert result.count(2) == 2, "count of 2 is wrong"


def check_reverse_twice_is_identity() -> None:
    data = list(range(10))
    twice = list(reversed(list(reversed(data))))
    assert twice == data, "double reverse did not restore original"


def check_dict_round_trip() -> None:
    pairs = [("alpha", 1), ("beta", 2), ("gamma", 3)]
    mapping = dict(pairs)
    assert dict(mapping.items()) == mapping, "dict items round trip failed"
    assert len(mapping) == len(pairs), "duplicate keys lost"


def check_integer_division_identity() -> None:
    for a in range(-20, 21):
        for b in (1, 2, 3, 7, -4):
            q, r = divmod(a, b)
            assert q * b + r == a, f"divmod identity failed for a={a}, b={b}"
            assert 0 <= r < abs(b) or r == 0, f"remainder out of range for a={a}, b={b}"


def check_gcd_divides_both() -> None:
    cases = [(12, 18), (35, 49), (17, 5), (0, 9), (100, 75)]
    for x, y in cases:
        g = math.gcd(x, y)
        assert g > 0, f"gcd not positive for ({x}, {y})"
        assert x % g == 0 and y % g == 0, f"gcd does not divide ({x}, {y})"


def check_float_addition_close() -> None:
    total = sum(0.1 for _ in range(10))
    assert math.isclose(total, 1.0, rel_tol=1e-9), f"sum was {total!r}"


def check_string_reverse_length() -> None:
    word = "invariant"
    assert len(word[::-1]) == len(word), "reversed string length differs"
    assert word[::-1][::-1] == word, "double string reverse failed"


def check_intentional_failure_range() -> None:
    values = [1, 2, 3, 4, 5]
    assert all(v < 5 for v in values), "value 5 is not less than 5"


def check_intentional_failure_parity() -> None:
    evens = [n for n in range(10) if n % 2 == 0]
    assert all(n % 2 == 1 for n in evens), "some evens are not odd"


def check_list_index_consistency() -> None:
    items = ["a", "b", "c", "d"]
    for i, item in enumerate(items):
        assert items.index(item) == i, f"index mismatch for {item!r}"


INVARIANTS: tuple[Invariant, ...] = (
    Invariant("sorted_after_sort", "sorted() yields ascending order", check_sorted_after_sort),
    Invariant("sort_preserves_elements", "sorting keeps the multiset of elements", check_sort_preserves_elements),
    Invariant("reverse_twice_identity", "reversing twice restores the list", check_reverse_twice_is_identity),
    Invariant("dict_round_trip", "dict items round-trip through dict()", check_dict_round_trip),
    Invariant("divmod_identity", "q*b + r == a with bounded remainder", check_integer_division_identity),
    Invariant("gcd_divides_both", "gcd divides both operands", check_gcd_divides_both),
    Invariant("float_sum_close", "ten 0.1 values sum to about 1.0", check_float_addition_close),
    Invariant("string_reverse", "string reverse preserves length and is involutive", check_string_reverse_length),
    Invariant("intentional_range_failure", "all values are below 5 (deliberately false)", check_intentional_failure_range),
    Invariant("intentional_parity_failure", "all evens are odd (deliberately false)", check_intentional_failure_parity),
    Invariant("list_index_consistency", "list.index matches enumerate positions", check_list_index_consistency),
)


def run_invariants(invariants: tuple[Invariant, ...]) -> tuple[list[str], list[tuple[str, str]]]:
    passed: list[str] = []
    failed: list[tuple[str, str]] = []
    for inv in invariants:
        try:
            inv.check()
        except AssertionError as exc:
            message = str(exc) or "assertion failed with no message"
            failed.append((inv.name, message))
        else:
            passed.append(inv.name)
    return passed, failed


def main() -> None:
    passed, failed = run_invariants(INVARIANTS)
    total = len(INVARIANTS)

    print("Invariant check report")
    print("=" * 40)
    for name in passed:
        print(f"[PASS] {name}")
    for name, message in failed:
        print(f"[FAIL] {name}: {message}")
    print("-" * 40)
    print(f"Total: {total}  Passed: {len(passed)}  Failed: {len(failed)}")

    if failed:
        print("Failed invariants:")
        for name, _ in failed:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
