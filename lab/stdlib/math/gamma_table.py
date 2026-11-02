import math

def factorial_ratio(n):
    return math.gamma(n + 1.0) / math.gamma(n)

def log_factorial(n):
    return math.lgamma(n + 1.0)

def main():
    for n in [1.0, 2.0, 3.0, 4.0, 5.0, 10.0]:
        print(n, round(math.gamma(n), 8), round(log_factorial(n), 8))
    print("ratio", round(factorial_ratio(6.0), 8))
    print("half", round(math.gamma(0.5), 8), round(math.gamma(-0.5), 8))
    print("erf", round(math.erf(1.0), 8), round(math.erfc(1.0), 8))
    try:
        print(math.gamma(0.0))
    except ValueError as exc:
        print("gamma failed:", exc)
    try:
        print(math.lgamma(0.0))
    except ValueError as exc:
        print("lgamma failed:", exc)

main()
