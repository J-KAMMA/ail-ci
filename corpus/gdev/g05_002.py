# task: Build a dictionary mapping each word length to the list of words of that length from a fixed word list.
from collections import defaultdict


WORD_LIST: tuple[str, ...] = (
    "apple", "banana", "cherry", "date", "elderberry", "fig", "grape",
    "honeydew", "kiwi", "lemon", "mango", "nectarine", "orange", "papaya",
    "quince", "raspberry", "strawberry", "tangerine", "ugli", "vanilla",
    "watermelon", "xigua", "yam", "zucchini", "apricot", "blueberry",
    "coconut", "dragonfruit", "eggplant", "feijoa", "gooseberry", "huckleberry",
    "jackfruit", "kumquat", "lime", "melon", "olive", "peach", "pear",
    "plum", "pomegranate", "rhubarb", "tomato", "cranberry", "lychee",
    "guava", "durian", "carambola", "boysenberry", "ackee",
)


def build_length_index(words: tuple[str, ...]) -> dict[int, list[str]]:
    """Map each word length to the sorted list of unique words of that length."""
    index: defaultdict[int, set[str]] = defaultdict(set)
    for word in words:
        index[len(word)].add(word)
    return {length: sorted(group) for length, group in sorted(index.items())}


def main() -> None:
    index: dict[int, list[str]] = build_length_index(WORD_LIST)
    for length, words in index.items():
        print(f"{length}: {words}")


if __name__ == "__main__":
    main()
