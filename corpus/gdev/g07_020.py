# task: Write a script that generates all permutations of a three-element list using itertools and prints them in sorted order.
import itertools


def main() -> None:
    items: list[int] = [1, 2, 3]
    perms: list[tuple[int, ...]] = sorted(itertools.permutations(items))
    for perm in perms:
        print(perm)


if __name__ == "__main__":
    main()
