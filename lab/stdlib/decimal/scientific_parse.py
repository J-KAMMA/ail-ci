from decimal import Decimal, InvalidOperation, ROUND_UP, localcontext

samples = ["1.23e4", "-5E-3", "+7.0", "0.000001",
           "12345678901234567890", "Infinity", "-NaN", "1_000.5"]
for text in samples:
    try:
        d = Decimal(text)
        print(text, "->", str(d), repr(d), d.adjusted())
    except (InvalidOperation, ValueError) as exc:
        print(text, "->", type(exc).__name__)

for text in ["", "   ", "1.2.3", "e5", "--1", "1e", "0x10"]:
    try:
        print(text, "->", Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        print(repr(text), "->", type(exc).__name__)

print(Decimal("1E+5").is_normal(), Decimal("1E-100").is_normal())
with localcontext() as ctx:
    ctx.Emin = -10
    ctx.Emax = 10
    print(Decimal("1E-100").is_subnormal(),
          Decimal("1E-9").is_subnormal(),
          Decimal("1E+9").is_normal())
print(Decimal("0.0000001").adjusted(), Decimal("1000").adjusted())
print(Decimal("9.995").quantize(Decimal("0.01"), rounding=ROUND_UP))
print(Decimal("1E+3") == Decimal("1000"),
      Decimal("1.0E+3").same_quantum(Decimal("1e3")))
