import statistics


def main() -> None:
    growth: list[int] = [2, 8, 4, 16]
    print(statistics.geometric_mean(growth))
    print(statistics.harmonic_mean(growth))
    speeds: list[int] = [30, 60, 40]
    print(statistics.harmonic_mean(speeds))
    print(f"{statistics.geometric_mean(growth):.6f}")
    print(f"{statistics.harmonic_mean(growth):.6f}")


main()
