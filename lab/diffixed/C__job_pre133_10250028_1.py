# C?-job-pre133-10250028-1: Fraction prelude tuples
from fractions import Fraction

f = Fraction(7, 3)
print(f.as_integer_ratio())
print(divmod(f, Fraction(2, 3)))
print(divmod(Fraction(1, 2), f))
print(float(f) > 2.3)
print(Fraction(3, 4) + Fraction(1, 4))
print(Fraction(-5, 2).as_integer_ratio())
