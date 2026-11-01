from abc import ABC, abstractmethod


class Animal(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def sound(self) -> str:
        ...

    @abstractmethod
    def legs(self) -> int:
        ...

    def speak(self) -> str:
        return self.name + " says " + self.sound()


class Mammal(Animal):
    def legs(self) -> int:
        return 4

    def feed(self) -> str:
        return self.name + " feeds milk"


class Dog(Mammal):
    def sound(self) -> str:
        return "woof"


class Bird(Animal):
    def sound(self) -> str:
        return "tweet"

    def legs(self) -> int:
        return 2


animals = [Dog("rex"), Bird("tweety")]
for animal in animals:
    line = animal.speak() + " legs=" + str(animal.legs())
    if isinstance(animal, Mammal):
        line = line + " " + animal.feed()
    print(line)
