from decimal import Decimal, InvalidOperation

samples = ["0", "-0.00", "123.4500", "1E+7", "-4.20e-3",
           "Infinity", "-NaN", "sNaN"]

for text in samples:
    d = Decimal(text)
    sign, digits, exponent = d.as_tuple()
    if not d.is_finite():
        print(text, "special", sign, digits, exponent)
        continue
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    print(text, "sign", sign, "digits", digits,
          "exponent", exponent, "coefficient", coefficient)
    print("  leading zeros:", len(digits) - len(str(coefficient))
          if coefficient else len(digits))

for text in ["", "12x", "1.2.3"]:
    try:
        print(Decimal(text).as_tuple())
    except InvalidOperation as exc:
        print(repr(text), type(exc).__name__, exc)
