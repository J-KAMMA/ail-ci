# task: Compute the digital root and additive persistence for integers 1 through 10,000 and print the number with the greatest persistence.
def digit_sum(n: int) -> int:
    """Return the sum of the decimal digits of a non-negative integer."""
    return sum(int(digit) for digit in str(n))


def additive_persistence(n: int) -> int:
    """Return the number of digit-sum steps needed to reach a single digit."""
    steps = 0
    while n >= 10:
        n = digit_sum(n)
        steps += 1
    return steps


def digital_root(n: int) -> int:
    """Return the single digit obtained by repeatedly summing digits."""
    while n >= 10:
        n = digit_sum(n)
    return n


def main() -> None:
    limit: int = 10_000
    best_number: int = 1
    best_persistence: int = -1

    for number in range(1, limit + 1):
        persistence = additive_persistence(number)
        # Strictly greater keeps the smallest number among ties.
        if persistence > best_persistence:
            best_persistence = persistence
            best_number = number

    print(f"Number with greatest additive persistence in 1..{limit}: {best_number}")
    print(f"Additive persistence: {best_persistence}")
    print(f"Digital root: {digital_root(best_number)}")


if __name__ == "__main__":
    main()
