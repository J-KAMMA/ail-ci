# expect: maybe_positive=general show=typed main=typed
def maybe_positive(n: int) -> int:
    if n > 0:
        return n
    return None


def show(v: int) -> None:
    print(v)


def main() -> None:
    show(maybe_positive(2))
    print("ok")

main()
