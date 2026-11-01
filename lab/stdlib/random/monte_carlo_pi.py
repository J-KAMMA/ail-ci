import math
import random


def main() -> None:
    random.seed(31415)
    inside = 0
    trials = 20000
    for _ in range(trials):
        x = random.random()
        y = random.random()
        if x * x + y * y <= 1.0:
            inside = inside + 1
    estimate = 4.0 * inside / trials
    print("inside", inside, "of", trials)
    print("pi", "%.6f" % estimate)
    print("error", "%.6f" % abs(estimate - math.pi))
    noise = 0.0
    for _ in range(100):
        noise = noise + random.gauss(0.0, 1.0)
    print("gauss mean", "%.6f" % (noise / 100.0))
    print("uniform", "%.6f" % random.uniform(10.0, 20.0))
    print("uniform keyword", "%.6f" % random.uniform(a=-1.0, b=1.0))
    normal = 0.0
    for _ in range(100):
        normal = normal + random.normalvariate(0.0, 1.0)
    print("normal mean", "%.6f" % (normal / 100.0))


main()
