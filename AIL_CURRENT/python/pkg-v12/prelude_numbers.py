# -*- coding: utf-8 -*-
# prelude_numbers.py -- the `numbers` ABC hierarchy as Python source (numberslib.py injects it).
#
# CPython's numbers.py names five abstract base classes.  This runtime has no ABCMeta, so the
# classes are plain classes with the same inheritance order and the concrete methods a subclass
# normally inherits; the abstract methods are omitted.  numberslib.py lowers isinstance(),
# issubclass() and register() so that the builtin types, Fraction and Decimal are classified as
# CPython classifies them.


class Number:
    pass


class Complex(Number):
    def __bool__(self) -> bool:
        return self != 0


class Real(Complex):
    def conjugate(self):
        return +self

    @property
    def real(self):
        return +self

    @property
    def imag(self):
        return 0


class Rational(Real):
    def __float__(self) -> float:
        return int(self.numerator) / int(self.denominator)


class Integral(Rational):
    def __index__(self):
        return int(self)

    def __float__(self) -> float:
        return float(int(self))

    @property
    def numerator(self):
        return +self

    @property
    def denominator(self):
        return 1
