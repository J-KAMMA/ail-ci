# expect: Stack.__init__=typed Stack.add=typed Stack.flip=general pick=general show=typed main=typed
class Stack:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add(self, v: int) -> None:
        self.items.append(v)

    def flip(self) -> list[int]:
        return sorted(self.items)


def pick(n: int) -> int:
    if n > 0:
        return n
    return None


def show(v: int) -> None:
    s = Stack()
    s.add(v)
    xs: list[int] = s.flip()
    print(len(xs))


def main() -> None:
    show(pick(3))
    print("ok")

main()
