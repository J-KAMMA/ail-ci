import math

def normal_cdf(x, mean, sigma):
    z = (x - mean) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))

def normal_tail(x, mean, sigma):
    z = (x - mean) / (sigma * math.sqrt(2.0))
    return 0.5 * math.erfc(z)

def normal_pdf(x, mean, sigma):
    z = (x - mean) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2.0 * math.pi))

def main():
    mean = 100.0
    sigma = 15.0
    for score in (70.0, 85.0, 100.0, 115.0, 130.0):
        print(score, round(normal_cdf(score, mean, sigma), 6), round(normal_pdf(score, mean, sigma), 8))
    print("tail", round(normal_tail(130.0, mean, sigma), 8))
    print("total", round(normal_cdf(130.0, mean, sigma) + normal_tail(130.0, mean, sigma), 12))
    print("half", math.isclose(normal_cdf(mean, mean, sigma), 0.5))

main()
