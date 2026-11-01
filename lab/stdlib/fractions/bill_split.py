from fractions import Fraction


def parse_price(text):
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def main():
    items = [("coffee", "3.50"), ("bagel", "2.25"), ("juice", "4.75"), ("broken", "abc"), ("free", "0")]
    subtotal = Fraction(0)
    for name, text in items:
        price = parse_price(text)
        if price is None:
            print("skip", name)
            continue
        print(name, price)
        subtotal = subtotal + price
    tax = subtotal * Fraction(8, 100)
    tip = subtotal * Fraction("0.15")
    total = subtotal + tax + tip
    print("subtotal", subtotal, float(subtotal))
    print("tax", tax)
    print("tip", tip)
    print("total", total, float(total))
    share = total / 3
    print("share", share, round(share, 2))
    cents = int(total * 100)
    print("cents", cents, Fraction(cents, 100))
    try:
        print(total / 0)
    except ZeroDivisionError as exc:
        print(type(exc).__name__, str(exc))


main()
