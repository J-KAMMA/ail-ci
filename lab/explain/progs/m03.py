# expect: outer=general evens=general show=typed main=typed
def outer(n: int) -> int:
    def inner(x: int) -> int:
        ys = [x, "s"]
        return x
    return inner(n)


def evens(n: int) -> list[int]:
    out: list[int] = []
    for i in range(n):
        out.append(i)
        yield i
    return out


def show(v: int) -> None:
    print(v)


def main() -> None:
    show(outer(3))
    print("ok")

main()
