import ail_array as ta


def store(label: str, x: int):
    a = ta.zeros(2, ta.int64)
    try:
        a[1] = x
        print(label, a)
    except OverflowError as exc:
        print(label, "OverflowError", exc)


def full(label: str, x: int):
    try:
        print(label, ta.full(2, x, ta.int64))
    except OverflowError as exc:
        print(label, "OverflowError", exc)


def add(label: str, x: int):
    a = ta.array([1, -1, 9223372036854775807], ta.int64)
    try:
        print(label, a + x)
    except OverflowError as exc:
        print(label, "OverflowError", exc)
    try:
        print(label, ta.wrapping_add(a, x))
    except OverflowError as exc:
        print(label, "OverflowError", exc)
    try:
        print(label, ta.eq(a, x), ta.where(ta.lt(a, 0), a, x))
    except OverflowError as exc:
        print(label, "OverflowError", exc)


def put(label: str, x: int):
    a = ta.zeros(3, ta.int64)
    i = ta.array([0, 2], ta.int64)
    try:
        ta.put(a, i, x)
        print(label, a)
    except OverflowError as exc:
        print(label, "OverflowError", exc)


def arr(label: str, x: int):
    try:
        print(label, ta.array([1, x], ta.int64))
    except OverflowError as exc:
        print(label, "OverflowError", exc)


def main():
    big = 9223372036854775808
    for_each = 0
    store("2^63", big)
    store("2^63-1", big - 1)
    store("-2^63", -big)
    store("-2^63-1", -big - 1)
    store("2^64", big * 2)
    store("2^200", big ** 3 * 2 ** 11)
    full("2^63", big)
    full("-2^63-1", -big - 1)
    full("ok", -big)
    add("2^63", big)
    add("2^64", big * 2)
    add("-2^63-1", -big - 1)
    add("ok", 5)
    put("2^63", big)
    put("2^70", 2 ** 70)
    put("ok", 7)
    arr("2^63", big)
    arr("2^64", 2 ** 64)
    arr("ok", -big)
    print(for_each)


main()
