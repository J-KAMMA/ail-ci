import statistics


def main() -> None:
    dist = statistics.NormalDist(mu=100, sigma=15)
    print(dist.mean)
    print(dist.stdev)
    print(dist.pdf(115))
    print(dist.cdf(115))
    print(dist.inv_cdf(0.9))
    print(dist.quantiles(4))
    print(dist.samples(3, seed=42))


main()
