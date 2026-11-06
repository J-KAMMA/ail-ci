# expect: Registry.__init__=typed Registry.set=typed Registry.view=general maybe=general ordered=general show=general main=typed
class Registry:
    def __init__(self) -> None:
        self.n: int = 0

    def set(self, n: int) -> None:
        self.n = n

    def view(self) -> dict[str, int]:
        d = {}
        d["n"] = self.n
        return d


def maybe(n: int) -> int:
    if n > 0:
        return n
    return None


def ordered(xs: list[int]) -> list[int]:
    return sorted(xs)


def show(n: int) -> None:
    r = Registry()
    r.set(n)
    d: dict[str, int] = r.view()
    xs: list[int] = ordered([d["n"]])
    print(len(xs))


def main() -> None:
    show(maybe(2))
    print("ok")

main()
