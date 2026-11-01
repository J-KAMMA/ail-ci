import math

def mean(values):
    return math.fsum(values) / len(values)

def variance(values):
    average = mean(values)
    return math.fsum((x - average) ** 2 for x in values) / len(values)

def geometric(values):
    return math.prod(values, start=1) ** (1.0 / len(values))

def main():
    samples = [1.5, 2.25, 3.0, 4.75, 8.0]
    print("mean", round(mean(samples), 6))
    print("variance", round(variance(samples), 6))
    print("spread", round(math.sqrt(variance(samples)), 6))
    print("geometric", round(geometric(samples), 6))
    print("empty sum", math.fsum([]), "empty product", math.prod([], start=1))
    print("start", math.prod([2, 3, 4], start=5))
    print("close", math.isclose(mean([0.1, 0.2, 0.3]), 0.2))
    try:
        print(math.fsum([math.inf, -math.inf]))
    except ValueError as exc:
        print("fsum failed:", exc)

main()
