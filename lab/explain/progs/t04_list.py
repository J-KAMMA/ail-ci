# expect: fill=typed total=typed main=typed
def fill(n: int) -> list[int]:
    out: list[int] = []
    for i in range(n):
        out.append(i * i)
    return out


def total(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = t + x
    return t


def main() -> None:
    print(total(fill(4)))


main()
