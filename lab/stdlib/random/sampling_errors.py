import random


def main() -> None:
    random.seed(5)
    try:
        print(random.choice([]))
    except IndexError as error:
        print("IndexError", error)
    try:
        random.randrange(5, 5)
    except ValueError as error:
        print("ValueError", error)
    try:
        random.sample([1, 2, 3], 5)
    except ValueError as error:
        print("ValueError", error)
    try:
        random.randint(5, 1)
    except ValueError as error:
        print("ValueError", error)
    empty = random.sample([], 0)
    print("empty sample", empty)
    print("still working", random.randint(1, 10))


main()
