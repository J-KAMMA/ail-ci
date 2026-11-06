# expect: outer=general show=typed main=typed
def outer(n: int) -> int:
    def inner(x: int) -> int:
        ys = [x, "s"]
        return x
    return inner(n)


def show(v: int) -> None:
    print(v)


def main() -> None:
    show(outer(3))
    print("ok")

main()
