from abc import ABC


class SizedLike(ABC):
    @classmethod
    def __subclasshook__(cls, candidate):
        if cls is SizedLike:
            if any("__len__" in base.__dict__ for base in candidate.__mro__):
                return True
        return NotImplemented


class Bag:
    def __init__(self, items: list) -> None:
        self.items = items

    def __len__(self) -> int:
        return len(self.items)


class Plain:
    pass


for candidate in (Bag([1, 2]), Plain()):
    print(type(candidate).__name__, issubclass(type(candidate), SizedLike), isinstance(candidate, SizedLike))
