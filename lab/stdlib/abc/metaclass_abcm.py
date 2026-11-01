from abc import ABCMeta, abstractmethod


class Storage(metaclass=ABCMeta):
    def __init__(self) -> None:
        self.items = []

    @abstractmethod
    def put(self, value: int) -> None:
        ...

    @abstractmethod
    def get(self) -> int:
        ...

    def size(self) -> int:
        return len(self.items)


class Queue(Storage):
    def put(self, value: int) -> None:
        self.items.append(value)

    def get(self) -> int:
        return self.items.pop(0)


class Stack(Storage):
    def put(self, value: int) -> None:
        self.items.append(value)

    def get(self) -> int:
        return self.items.pop()


for cls in (Queue, Stack):
    store = cls()
    for value in (1, 2, 3):
        store.put(value)
    print(cls.__name__, store.size(), store.get(), store.get())
