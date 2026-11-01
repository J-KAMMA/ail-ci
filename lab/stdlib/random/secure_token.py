import random


def main() -> None:
    rng = random.SystemRandom()
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    print("".join(rng.choice(alphabet) for _ in range(12)))


main()
