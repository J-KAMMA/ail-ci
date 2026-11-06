"""Example 4: a raised Python exception becomes status 1 and a last_error string."""

__ail_name__ = "raiser"
__ail_export__ = ["checked_div", "require_positive"]


def checked_div(a: int, b: int) -> int:
    if b == 0:
        raise ValueError("division by zero")
    return a // b


def require_positive(n: int) -> int:
    if n <= 0:
        raise ValueError("value must be positive")
    return n


if __name__ == "__main__":
    print("checked_div(7, 2) = %d" % checked_div(7, 2))
    try:
        checked_div(1, 0)
    except ValueError as error:
        print("error: ValueError: %s" % error)
    try:
        require_positive(-3)
    except ValueError as error:
        print("error: ValueError: %s" % error)
    print("require_positive(5) = %d" % require_positive(5))
