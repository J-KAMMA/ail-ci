# expect: ordering=general evens=general maybe=general show=typed main=typed
def ordering(xs: list[int]) -> list[int]:
    return sorted(xs)


def evens(n: int) -> list[int]:
    out: list[int] = []
    for i in range(n):
        out.append(i)
        yield i
    return out


def maybe(n: int) -> int:
    if n > 0:
        return n
    return None


def show(v: int) -> None:
    print(v)


def main() -> None:
    show(maybe(2))
    print("ok")

main()
