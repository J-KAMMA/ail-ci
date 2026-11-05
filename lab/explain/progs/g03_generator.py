# expect: evens=general report=typed main=typed
def evens(n: int) -> list[int]:
    out: list[int] = []
    for i in range(n):
        out.append(i * 2)
        yield i * 2
    return out


def report(xs: list[int]) -> None:
    print(len(xs))


def main() -> None:
    report([1, 2, 3])
    print("ok")

main()
