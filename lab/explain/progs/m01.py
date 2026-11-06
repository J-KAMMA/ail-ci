# expect: ordering=general label=general show=general main=typed
def ordering(xs: list[int]) -> list[int]:
    return sorted(xs)


def label(n: int) -> list[int]:
    xs = [n, "many"]
    return [n]


def show(xs: list[int]) -> None:
    print(len(xs))


def main() -> None:
    show(ordering([2, 1]))
    print("ok")

main()
