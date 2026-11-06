# expect: run=typed main=typed
def run(n: int) -> int:
    total: int = 0

    def add(v: int) -> None:
        nonlocal total
        total = total + v

    add(n)
    add(n + 1)
    return total


def main() -> None:
    print(run(3))


main()
