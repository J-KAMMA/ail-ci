# expect: fact=typed fib=typed main=typed
def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)


def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def main() -> None:
    print(fact(5))
    print(fib(10))


main()
