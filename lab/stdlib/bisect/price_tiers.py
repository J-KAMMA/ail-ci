import bisect

TIERS = [0.0, 9.99, 24.99, 49.99, 99.99]
RATES = [0.0, 0.05, 0.10, 0.15, 0.20]


def rate(price):
    index = bisect.bisect_right(TIERS, price)
    if index == 0:
        return 0.0
    return RATES[index - 1]


def main():
    prices = [0.0, 5.0, 9.99, 10.0, 24.99, 25.0, 49.99, 50.0, 99.99, 100.0]
    total = 0.0
    for price in prices:
        share = rate(price)
        fee = price * share
        total += fee
        print(f"{price:.2f} {share:.2f} {fee:.2f}")
    print(f"total {total:.2f}")
    print("idx", bisect.bisect_left(TIERS, 25.0), bisect.bisect_right(TIERS, 25.0))
    print("edge", bisect.bisect_left(TIERS, 0.0), bisect.bisect_right(TIERS, 0.0))


main()
