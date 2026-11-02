import math

def future_value(principal, rate, years):
    return principal * math.pow(1.0 + rate, years)

def doubling_time(rate):
    return math.log(2.0) / math.log(1.0 + rate)

def real_return(amount, inflation, years):
    return amount / math.pow(1.0 + inflation, years)

def main():
    principal = 2500.0
    for rate in (0.01, 0.03, 0.07):
        value = future_value(principal, rate, 10)
        years = math.ceil(doubling_time(rate))
        print("rate", rate, "value", round(value, 2), "doubles in", years)
    adjusted = real_return(future_value(principal, 0.03, 10), 0.02, 10)
    print("real", round(adjusted, 2))
    print("unchanged", math.isclose(future_value(1000.0, 0.0, 5), 1000.0))
    try:
        print(math.log(0.0))
    except ValueError as exc:
        print("log failed:", exc)
    try:
        print(math.pow(-1.0, 0.5))
    except ValueError as exc:
        print("pow failed:", exc)

main()
