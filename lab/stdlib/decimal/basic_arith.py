from decimal import Decimal

prices = [Decimal("19.99"), Decimal("5.50"), Decimal("3.25")]
total = Decimal(0)
for price in prices:
    total = total + price
print(total)
print(total / Decimal(len(prices)))
print(total * 2)
print(total - Decimal("10"))
print(Decimal(7) / Decimal(2))
print(Decimal("1.5") + 2)
print(2 + Decimal("1.5"))
print(Decimal("10") // Decimal("3"))
print(Decimal("10") % Decimal("3"))
print(divmod(Decimal("10"), Decimal("3")))
print(-Decimal("2.5"), +Decimal("-2.5"), abs(Decimal("-2.5")))
print(Decimal("1.10") == Decimal("1.1"), Decimal("1.1") < 2)
print(bool(Decimal("0")), bool(Decimal("-0.00")), bool(Decimal("0.01")))
print(int(Decimal("42.9")), float(Decimal("0.5")))
print(str(Decimal("1E+3")), repr(Decimal("1E+3")))
