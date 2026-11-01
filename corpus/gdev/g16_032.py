# task: Use itertools.permutations on a fixed string to count the permutations that contain no two identical adjacent characters and print the count.
from itertools import permutations


def has_no_adjacent_duplicates(seq: tuple[str, ...]) -> bool:
    return all(a != b for a, b in zip(seq, seq[1:]))


def main() -> None:
    text: str = "aabbc"
    count: int = 0
    for perm in permutations(text):
        if has_no_adjacent_duplicates(perm):
            count += 1
    print(f"Permutations of {text!r} with no identical adjacent characters: {count}")


if __name__ == "__main__":
    main()
