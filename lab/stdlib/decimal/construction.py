from decimal import Decimal, InvalidOperation

values = ["0", "-0", "123.4500", "1e-7", ".5", "5.", " 12.5 ",
          "Infinity", "-inf", "NaN", "sNaN"]
for text in values:
    d = Decimal(text)
    print(repr(d), d.is_finite(), d.is_nan(), d.is_snan(),
          d.is_infinite(), d.is_signed())
print(Decimal(42), Decimal(True), Decimal(Decimal("1.25")))
print(Decimal.from_float(0.1))
print(Decimal((1, (1, 2, 3, 4), -2)))
print(Decimal((0, (0,), -3)))
d = Decimal("-12.50")
print(d.as_integer_ratio())
print(d.copy_abs(), d.copy_negate(), d.copy_sign(Decimal("3")))
print(d.adjusted(), d.conjugate())
for bad in ["", "1,000", "12x", None]:
    try:
        print(Decimal(bad))
    except (InvalidOperation, TypeError) as exc:
        print(type(exc).__name__, exc)
