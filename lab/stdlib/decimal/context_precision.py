from decimal import (ROUND_HALF_UP, Context, Decimal, getcontext,
                     localcontext, setcontext)

print(getcontext().prec, getcontext().rounding, getcontext().Emin,
      getcontext().Emax)
print(Decimal("1") / Decimal("3"))
with localcontext() as ctx:
    ctx.prec = 5
    print(Decimal("1") / Decimal("3"))
    ctx.rounding = ROUND_HALF_UP
    print(Decimal("2.345").quantize(Decimal("0.01")))
print(getcontext().prec)

old = getcontext().copy()
new = Context(prec=6, rounding=ROUND_HALF_UP, Emin=-100, Emax=100,
              capitals=0)
setcontext(new)
print(Decimal("1") / Decimal("7"))
print(Decimal("1E+10") / Decimal("3"))
setcontext(old)
print(getcontext().prec)

ctx = Context(prec=3)
print(ctx.prec, ctx.Etiny(), ctx.Etop())
print(ctx.create_decimal("12.3456"))
ctx2 = Context(prec=2, rounding="ROUND_DOWN")
print(ctx2.create_decimal(Decimal("999")))
try:
    ctx.prec = 0
except ValueError as exc:
    print(type(exc).__name__, exc)
