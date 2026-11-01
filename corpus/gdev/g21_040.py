# task: Serialize a dictionary of word frequencies computed from a fixed sentence and print the JSON with keys sorted by frequency.
import json
import re
from collections import Counter

SENTENCE: str = (
    "The quick brown fox jumps over the lazy dog. "
    "The dog barks, the fox runs, and the quick cat watches the fox "
    "while the lazy dog sleeps."
)


def compute_frequencies(text: str) -> Counter[str]:
    words: list[str] = re.findall(r"[a-z']+", text.lower())
    return Counter(words)


def sorted_by_frequency(counts: Counter[str]) -> dict[str, int]:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {word: count for word, count in ordered}


def main() -> None:
    counts: Counter[str] = compute_frequencies(SENTENCE)
    ordered: dict[str, int] = sorted_by_frequency(counts)
    print(json.dumps(ordered, indent=2))


if __name__ == "__main__":
    main()
