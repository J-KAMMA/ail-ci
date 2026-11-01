import math

def decompose(value):
    fraction, exponent = math.frexp(value)
    return fraction, exponent

def rebuild(fraction, exponent):
    return math.ldexp(fraction, exponent)

def split(value):
    frac, whole = math.modf(value)
    return frac, whole

def main():
    for value in [0.0, 1.0, 8.0, -3.25, 0.1]:
        fraction, exponent = decompose(value)
        print(value, fraction, exponent, rebuild(fraction, exponent))
    frac, whole = split(3.25)
    print("split", frac, whole)
    print("sign", math.copysign(1.0, -3.25))
    print("ulp", math.ulp(1.0), math.ulp(0.0))
    print("next", math.nextafter(1.0, math.inf))

main()
