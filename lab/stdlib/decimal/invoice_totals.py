from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28
items = [
    ("Widget", Decimal("12.99"), 3),
    ("Gasket", Decimal("0.75"), 12),
    ("Bolt", Decimal("0.10"), 250),
    ("Service", Decimal("45.00"), 1),
]
print("Invoice")
subtotal = Decimal("0")
for name, price, qty in items:
    line = price * qty
    subtotal += line
    print(f"{name:<10} {qty:>3} {line:>10.2f}")

tax_rate = Decimal("0.0825")
tax = (subtotal * tax_rate).quantize(Decimal("0.01"),
                                     rounding=ROUND_HALF_UP)
total = (subtotal + tax).quantize(Decimal("0.01"),
                                  rounding=ROUND_HALF_UP)
print(f"subtotal  {subtotal:>10.2f}")
print(f"tax       {tax:>10.2f}")
print(f"total     {total:>10.2f}")

budget = Decimal("300.00")
print("within budget:", total <= budget)
print("remaining:", (budget - total).quantize(Decimal("0.01")))
print("largest line:", max(price * qty for _, price, qty in items))
print("smallest line:", min(price * qty for _, price, qty in items))
rounded_up = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
print("rounded total:", rounded_up)
