from datetime import timedelta


def show(label: str, td: timedelta) -> None:
    print(label, td, repr(td), td.days, td.seconds, td.microseconds, td.total_seconds())


def main() -> None:
    a = timedelta(hours=2, minutes=30, seconds=15, milliseconds=250, microseconds=7)
    b = timedelta(seconds=95)
    negative = -b
    show("a", a)
    show("b", b)
    show("neg", negative)
    show("sum", a + b)
    show("diff", a - b)
    show("scaled", a * 3)
    show("half", a / 2)
    show("floor", a // 2)
    print("ratio", a / b, "whole", a // b)
    show("mod", a % b)
    print("abs", abs(negative), "bool", bool(negative), bool(timedelta()))
    print("compare", a > b, b < a, a == a, negative == b * -1)
    try:
        timedelta(days=1000000000)
    except OverflowError as e:
        print("overflow", type(e).__name__)
    try:
        a.total_seconds()
    except Exception as e:
        print("unexpected", e)


main()
