from decimal import (Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN,
                     ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext)

amounts = [Decimal("1.005"), Decimal("2.675"), Decimal("3.14159"),
           Decimal("-2.5"), Decimal("0")]
for amount in amounts:
    print(amount.quantize(Decimal("0.01")),
          amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    print(amount.quantize(Decimal("0.1"), rounding=ROUND_DOWN),
          amount.quantize(Decimal("1"), rounding=ROUND_CEILING))
    print(amount.quantize(Decimal("1"), rounding=ROUND_FLOOR),
          amount.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN))

for value in [Decimal("2.5"), Decimal("3.5"), Decimal("-2.5"), Decimal("2.4")]:
    print(round(value), round(value, 1), int(value),
          value.to_integral_value(), value.to_integral_exact())

print(Decimal("123.456").to_integral_value(rounding=ROUND_FLOOR))
print(Decimal("1E+5").quantize(Decimal("1e3")))
print(Decimal("9.995").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
with localcontext() as ctx:
    ctx.prec = 4
    print(Decimal("1.23456") + Decimal("0"))
    try:
        print(Decimal("12345").quantize(Decimal("1")))
    except InvalidOperation as exc:
        print(type(exc).__name__, exc)
