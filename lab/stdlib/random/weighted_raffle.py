import random


def main() -> None:
    random.seed(8)
    people = ["ada", "bob", "cy", "dee", "eve"]
    weights = [5, 1, 3, 2, 4]
    winners = random.choices(people, weights=weights, k=5)
    print("winners", winners)
    counts = {}
    for person in winners:
        counts[person] = counts.get(person, 0) + 1
    print("counts", sorted(counts.items()))
    print("positional", random.choices(people, weights, k=3))
    print("uniform", random.choices(people, k=4))


main()
