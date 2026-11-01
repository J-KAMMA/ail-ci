# task: Write a script that counts the distinct words in a hardcoded paragraph by converting it to a set and prints the count.
import re


PARAGRAPH: str = (
    "The quick brown fox jumps over the lazy dog. The dog barks, and the fox "
    "runs away! Later, the quick fox returns to the forest, where the brown "
    "bear sleeps. Nobody knows why the fox never stops; perhaps it is simply "
    "curious about the world beyond the forest's edge."
)


def extract_words(text: str) -> list[str]:
    """Return lowercase words, ignoring punctuation and case."""
    return re.findall(r"[a-z']+", text.lower())


def count_distinct_words(text: str) -> int:
    """Count distinct words in the text by converting the word list to a set."""
    words: set[str] = set(extract_words(text))
    return len(words)


def main() -> None:
    count: int = count_distinct_words(PARAGRAPH)
    print(f"Distinct words: {count}")


if __name__ == "__main__":
    main()
