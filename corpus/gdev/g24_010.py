# task: Write a script that uses fractions.Fraction to compute and print the exact probability that two dice sum to seven.
from fractions import Fraction


def main() -> None:
    faces: range = range(1, 7)
    outcomes: list[tuple[int, int]] = [(a, b) for a in faces for b in faces]
    total: int = len(outcomes)
    favorable: int = sum(1 for a, b in outcomes if a + b == 7)
    probability: Fraction = Fraction(favorable, total)
    print(f"Favorable outcomes: {favorable}")
    print(f"Total outcomes: {total}")
    print(f"Probability that two dice sum to 7: {probability}")
    print(f"As a decimal approximation: {float(probability):.4f}")


if __name__ == "__main__":
    main()
