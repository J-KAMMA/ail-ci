# task: Demonstrate binary floating-point representation error by printing 0.1 + 0.2 and its exact value using the fractions and decimal modules.
from decimal import Decimal, localcontext
from fractions import Fraction


def main() -> None:
    a: float = 0.1
    b: float = 0.2
    total: float = a + b

    print("Binary floating-point representation error demo")
    print("=" * 48)

    # Naive float result and its shortest round-trip representation
    print(f"0.1 + 0.2 (float, repr)      : {total!r}")
    print(f"0.1 + 0.2 (float, 17 digits) : {total:.17f}")
    print(f"0.3 literal (float, repr)    : {0.3!r}")
    print(f"Equal to 0.3?                : {total == 0.3}")
    print()

    # Exact values of the stored binary doubles (Fraction)
    frac_a = Fraction(a)
    frac_b = Fraction(b)
    frac_exact_sum = frac_a + frac_b
    frac_stored_result = Fraction(total)
    frac_error = frac_stored_result - frac_exact_sum

    print("Exact values using fractions.Fraction:")
    print(f"  Fraction(0.1)            = {frac_a}")
    print(f"  Fraction(0.2)            = {frac_b}")
    print(f"  Exact sum of stored inputs = {frac_exact_sum}")
    print(f"  Fraction(0.1 + 0.2)      = {frac_stored_result}")
    print(f"  Rounding error (float - exact) = {frac_error}")
    print(f"  Rounding error as float  = {float(frac_error)!r}")
    print()

    # Exact decimal expansions using decimal (Decimal(float) is exact)
    dec_a = Decimal(a)
    dec_b = Decimal(b)
    dec_stored_result = Decimal(total)

    with localcontext() as ctx:
        # High precision so the sum of two exact binary expansions is not rounded
        ctx.prec = 120
        dec_exact_sum = dec_a + dec_b
        dec_error = dec_stored_result - dec_exact_sum

    print("Exact decimal expansions using decimal.Decimal:")
    print(f"  Decimal(0.1)              = {dec_a}")
    print(f"  Decimal(0.2)              = {dec_b}")
    print(f"  Exact decimal sum of inputs = {dec_exact_sum}")
    print(f"  Decimal(0.1 + 0.2)        = {dec_stored_result}")
    print(f"  Rounding error (decimal)  = {dec_error}")
    print()

    # Cross-check: the two exact representations agree
    print("Consistency check:")
    print(f"  Fraction and Decimal sums agree? "
          f"{Fraction(dec_exact_sum) == frac_exact_sum}")
    print(f"  Stored result equals exact sum?  "
          f"{frac_stored_result == frac_exact_sum}")


if __name__ == "__main__":
    main()
