from decimal import (ROUND_05UP, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR,
                     ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP,
                     Context, Decimal, localcontext)

modes = [ROUND_UP, ROUND_DOWN, ROUND_CEILING, ROUND_FLOOR,
         ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_05UP]
values = ["2.5", "3.5", "-2.5", "-3.5", "1.25", "2.45"]
for mode in modes:
    with localcontext() as ctx:
        ctx.rounding = mode
        row = []
        for text in values:
            row.append(str(Decimal(text).quantize(Decimal("1"))))
        print(mode, " ".join(row))

for mode in modes:
    with localcontext() as ctx:
        ctx.rounding = mode
        print(mode,
              Decimal("2.4").quantize(Decimal("0.5")),
              Decimal("-2.4").quantize(Decimal("0.5")),
              Decimal("1.2345").quantize(Decimal("0.001")))

base = Context(prec=8, rounding=ROUND_HALF_EVEN)
with localcontext(base) as ctx:
    ctx.prec = 5
    print("local prec", Decimal("1") / Decimal("9"))
print("base prec", base.prec, base.rounding)
print(Decimal("5.5").to_integral_value(rounding=ROUND_HALF_DOWN))
