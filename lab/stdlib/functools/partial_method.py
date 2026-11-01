"""Formatting methods specialised with functools.partialmethod."""
from functools import partialmethod


class Formatter:
    def __init__(self, unit):
        self.unit = unit

    def render(self, value, precision=2, prefix=""):
        return f"{prefix}{value:.{precision}f}{self.unit}"

    money = partialmethod(render, precision=2, prefix="$")
    ratio = partialmethod(render, precision=1)
    exact = partialmethod(render, precision=0)


def main() -> None:
    kg = Formatter(" kg")
    usd = Formatter("")
    print(kg.money(12.345))
    print(kg.ratio(0.5))
    print(kg.exact(7.6))
    print(usd.money(3))
    print(usd.render(1.25))
    print(kg.render(2.5, 3, "~"))


main()
