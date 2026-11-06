# expect: label=general show=typed main=typed
def label(n: int) -> list[int]:
    xs = [n, "many"]
    return [n]


def show(xs: list[int]) -> None:
    print(len(xs))


def main() -> None:
    show([1, 2])
    print("ok")

main()
