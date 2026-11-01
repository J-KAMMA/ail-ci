from decimal import Decimal, InvalidOperation, localcontext

print(Decimal("2") ** 3, Decimal("2") ** -2, Decimal("1.5") ** 2)
print(Decimal("-2") ** 3, Decimal("-2") ** 2)
print(Decimal("2").sqrt(), Decimal("0").sqrt(), Decimal("0.25").sqrt())
print(Decimal("9").sqrt())
with localcontext() as ctx:
    ctx.prec = 10
    print(Decimal("2").sqrt())
    print(Decimal("1.23456789") ** 5)
print(Decimal("3.7").max(Decimal("3.70")),
      Decimal("3.7").min(Decimal("3.70")))
print(Decimal("1.2300").normalize(), Decimal("1000").normalize(),
      Decimal("0.000").normalize())
print(Decimal("-0").normalize().is_signed())
print(Decimal("2.5").compare(Decimal("2.50")))
try:
    print(Decimal("NaN").compare(Decimal("1")))
except InvalidOperation as exc:
    print(type(exc).__name__, exc)
try:
    print(Decimal("-1").sqrt())
except InvalidOperation as exc:
    print(type(exc).__name__, exc)

total = Decimal("1")
for step in range(1, 6):
    total = total * Decimal(step)
print(total, total.sqrt(), total / Decimal(3))
