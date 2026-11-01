from enum import Enum


Color = Enum("Color", "RED GREEN BLUE")
Sized = Enum("Sized", [("SMALL", 1), ("LARGE", 2)])
Explicit = Enum("Explicit", {"LOW": 1, "HIGH": 10})


def main():
    print(list(Color))
    print(Color["GREEN"], Color(3).name)
    print([(member.name, member.value) for member in Sized])
    print(Explicit.HIGH.value, list(Explicit.__members__))


main()
