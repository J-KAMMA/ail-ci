def safe_div(a: int, b: int) -> int:
    try:
        q = a // b
    except ZeroDivisionError:
        q = -1
    return q


def main() -> None:
    print(safe_div(10, 3))
    print(safe_div(1, 0))


main()
