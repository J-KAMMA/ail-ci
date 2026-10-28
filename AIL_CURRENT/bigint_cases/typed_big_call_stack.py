def make() -> int:
    x = 1; i = 0
    while i < 70:
        x = x * 2; i += 1
    return x
class Stack:
    def __init__(self):
        self.items: list[int] = []
    def push(self, v: int) -> None:
        self.items.append(v)
    def pop(self) -> int:
        return self.items.pop()
def main() -> None:
    s = Stack()
    s.push(make())
    print(s.pop())
main()
