from decimal import Decimal

d = Decimal("1234567.891")
print(f"{d}")
print(f"{d:.2f}", f"{d:,.2f}", f"{d:e}", f"{d:E}", f"{d:g}", f"{d:G}")
print(f"{d:+015.2f}", f"{d:^20.2f}", f"{d:<20.2f}", f"{d:>20.2f}")
print(f"{Decimal('0.0042'):.2%}", f"{Decimal('-0.5'):f}",
      f"{Decimal('1E+6'):f}")
print(format(Decimal("12.3"), ".4f"), format(Decimal("12.3"), "08.2f"))
print(format(Decimal("-0.0"), "z.1f"), f"{Decimal('1.5'): }")
print(Decimal("1.234E+7").to_eng_string())
print(Decimal("123456789").to_eng_string())
print(str(Decimal("1E+3")), repr(Decimal("1E+3")))
print(str(Decimal("-0.00")), repr(Decimal("NaN")),
      repr(Decimal("Infinity")))
print(f"{Decimal('255'):#.0f}")
print(f"{Decimal('1234.5'):010.2f}", f"{Decimal('1234.5'):010,.2f}")
print(f"{Decimal('1.23456789'):.3}", f"{Decimal('1.23456789'):.0f}")
