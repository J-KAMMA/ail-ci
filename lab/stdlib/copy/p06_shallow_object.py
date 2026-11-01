import copy

class Box:
    def __init__(self, name: str, values: list) -> None:
        self.name = name
        self.values = values

    def total(self) -> int:
        return sum(self.values)

def main() -> None:
    original = Box("first", [1, 2])
    shallow = copy.copy(original)
    shallow.name = "second"
    shallow.values.append(3)
    print(original.name, shallow.name)
    print(original.values, shallow.values)
    print(original.values is shallow.values)
    print(original.total(), shallow.total())
    print(type(shallow).__name__)

main()
