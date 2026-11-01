import random


class Simulation:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.total = 0

    def draw(self) -> int:
        value = self.rng.randint(1, 6)
        self.total = self.total + value
        return value


def main() -> None:
    sim = Simulation(2025)
    rolls = []
    for _ in range(10):
        rolls.append(sim.draw())
    print("rolls", rolls, "total", sim.total)
    rng = random.Random(77)
    print("random", rng.random())
    print("range", rng.randrange(10, 100, 5))
    items = ["a", "b", "c", "d"]
    rng.shuffle(items)
    print("shuffled", items)
    print("picked", rng.sample(items, 2))
    print("weighted", rng.choices(items, weights=[1, 2, 3, 4], k=4))
    print("bits", rng.getrandbits(12))


main()
