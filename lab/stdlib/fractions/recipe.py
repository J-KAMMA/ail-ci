from fractions import Fraction


class Recipe:
    def __init__(self, name, servings):
        self.name = name
        self.servings = servings
        self.items = {}

    def add(self, item, amount):
        self.items[item] = amount

    def scaled(self, servings):
        factor = Fraction(servings, self.servings)
        out = Recipe(self.name + "*", servings)
        for item in self.items:
            out.add(item, self.items[item] * factor)
        return out

    def total(self):
        t = Fraction(0)
        for item in self.items:
            t = t + self.items[item]
        return t


def main():
    r = Recipe("bread", 4)
    r.add("flour", Fraction(3, 2))
    r.add("water", Fraction("0.75"))
    r.add("salt", Fraction(1, 8))
    print(r.name, r.servings, r.total())
    for item in sorted(r.items):
        print(item, r.items[item], float(r.items[item]))
    twice = r.scaled(8)
    print(twice.name, twice.total())
    for item in sorted(twice.items):
        print(item, twice.items[item], twice.items[item].as_integer_ratio())
    try:
        r.add("bad", Fraction(1, 0))
    except ZeroDivisionError as exc:
        print(type(exc).__name__, str(exc))


main()
