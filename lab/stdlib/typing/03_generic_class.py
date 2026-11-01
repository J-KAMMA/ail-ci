from typing import Generic, List, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value

    def set(self, value: T) -> None:
        self.value = value


class Stack(Generic[T]):
    def __init__(self) -> None:
        self.items: List[T] = []

    def push(self, item: T) -> None:
        self.items.append(item)

    def pop(self) -> T:
        return self.items.pop()

    def size(self) -> int:
        return len(self.items)


def main() -> None:
    b: Box[int] = Box(3)
    print(b.get())
    b.set(9)
    print(b.get())
    s: Stack[str] = Stack()
    s.push("a")
    s.push("b")
    print(s.size(), s.pop(), s.size())
    words = Box("hello")
    print(words.get().upper())


main()
