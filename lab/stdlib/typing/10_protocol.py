from typing import Protocol


class Greeter(Protocol):
    def greet(self) -> str: ...


class Person:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return "hi " + self.name


class Robot:
    def __init__(self, model: str) -> None:
        self.model = model

    def greet(self) -> str:
        return "beep " + self.model


def welcome(g: Greeter) -> str:
    return "[" + g.greet() + "]"


def main() -> None:
    people = [Person("ada"), Person("bob")]
    bots = [Robot("r2"), Robot("c3")]
    for p in people:
        print(welcome(p))
    for b in bots:
        print(welcome(b))


main()
