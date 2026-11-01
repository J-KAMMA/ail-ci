from decimal import Decimal, DivisionByZero, InvalidOperation

pairs = [("10", "3"), ("-10", "3"), ("10", "-3"), ("-10", "-3"),
         ("1", "8"), ("0", "7")]
for a, b in pairs:
    x, y = Decimal(a), Decimal(b)
    print(x // y, x % y, divmod(x, y))
print(Decimal("-7") // Decimal("2"), Decimal("-7") % Decimal("2"))
print(Decimal("7.5") // Decimal("2"), Decimal("7.5") % Decimal("2"))
print(Decimal("1.00") % Decimal("0.10"))
print(Decimal("5.5") // Decimal("1.5"), Decimal("5.5") % Decimal("1.5"))

for a, b in [("1", "0"), ("0", "0")]:
    try:
        print(Decimal(a) / Decimal(b))
    except (DivisionByZero, InvalidOperation) as exc:
        print(type(exc).__name__, exc)

for a, b in [("1.5", "0"), ("0", "2")]:
    try:
        print(Decimal(a) // Decimal(b), Decimal(a) % Decimal(b))
    except (DivisionByZero, InvalidOperation) as exc:
        print(type(exc).__name__, exc)

try:
    print(divmod(Decimal("1"), Decimal("0")))
except (DivisionByZero, InvalidOperation) as exc:
    print(type(exc).__name__, exc)
