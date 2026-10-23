# task: Use itertools.groupby on a sorted list of fixed words to count the words for each first letter and print the counts.
from itertools import groupby


def main() -> None:
    words: list[str] = [
        "apple",
        "banana",
        "apricot",
        "blueberry",
        "cherry",
        "cranberry",
        "date",
        "elderberry",
        "fig",
        "grape",
        "guava",
        "honeydew",
        "kiwi",
        "lemon",
        "lime",
        "mango",
        "nectarine",
        "orange",
        "papaya",
        "peach",
        "pear",
        "plum",
        "quince",
        "raspberry",
        "strawberry",
        "tangerine",
        "ugli",
        "vanilla",
        "watermelon",
        "yam",
        "zucchini",
    ]

    sorted_words: list[str] = sorted(words)

    for letter, group in groupby(sorted_words, key=lambda w: w[0]):
        count: int = sum(1 for _ in group)
        print(f"{letter}: {count}")


if __name__ == "__main__":
    main()
