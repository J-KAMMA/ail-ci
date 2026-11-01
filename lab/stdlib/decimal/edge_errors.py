from decimal import (Decimal, DecimalException, DivisionByZero,
                     InvalidOperation, Overflow, localcontext)


def show(label, fn):
    try:
        print(label, fn())
    except (DecimalException, TypeError) as exc:
        print(label, type(exc).__name__, exc)


show("bad string", lambda: Decimal("abc"))
show("empty string", lambda: Decimal("") + Decimal("1"))
show("divide zero", lambda: Decimal("1") / Decimal("0"))
show("zero over zero", lambda: Decimal("0") / Decimal("0"))
show("floor by zero", lambda: Decimal("1.5") // Decimal("0"))
show("mod by zero", lambda: Decimal("1.5") % Decimal("0"))
show("inf minus inf", lambda: Decimal("Infinity") - Decimal("Infinity"))
show("nan add", lambda: Decimal("NaN") + Decimal("1"))
show("bad operand", lambda: Decimal("1") + "2")
try:
    print("bad rounding", Decimal("1").quantize(Decimal("1"),
                                                rounding="ROUND_NOPE"))
except Exception as exc:
    print("bad rounding", type(exc).__name__, exc)

with localcontext() as ctx:
    ctx.Emax = 9
    try:
        print(Decimal("1E8") * Decimal("1E8"))
    except Overflow as exc:
        print("overflow", type(exc).__name__, exc)

with localcontext() as ctx:
    ctx.prec = 3
    print("prec", Decimal("1.23456") + Decimal("0"))
    print("prec mul", Decimal("12.34") * Decimal("5.67"))
