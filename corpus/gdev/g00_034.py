# task: Write a script that estimates the syllable count of each word in a hardcoded sentence using a vowel-group heuristic.
import re


SENTENCE: str = (
    "The quick brown fox jumps over the lazy dog, "
    "but unpredictable weather rarely interrupts beautiful gardens."
)

VOWELS: str = "aeiouy"


def extract_words(text: str) -> list[str]:
    """Return alphabetic words from the text, preserving order."""
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)*", text)


def estimate_syllables(word: str) -> int:
    """Estimate syllables by counting vowel groups with simple adjustments."""
    w: str = word.lower()
    if not w:
        return 0

    # Count contiguous groups of vowels (including 'y').
    groups: int = 0
    in_group: bool = False
    for ch in w:
        if ch in VOWELS:
            if not in_group:
                groups += 1
                in_group = True
        else:
            in_group = False

    count: int = groups

    # Silent trailing 'e' (but not "le" after a consonant, as in "table").
    if len(w) > 2 and w.endswith("e") and w[-2] not in VOWELS:
        if not (w.endswith("le") and w[-3] not in VOWELS):
            count -= 1

    # Words ending in "es" or "ed" often do not add a syllable,
    # unless preceded by a sound that requires it (t, d, s, x, z, ch, sh).
    if len(w) > 2 and (w.endswith("es") or w.endswith("ed")):
        prev: str = w[-3]
        if w.endswith("ed") and prev not in "td":
            count -= 1
        elif w.endswith("es") and prev not in "sxz" and w[-4:-2] not in ("ch", "sh"):
            count -= 1

    return max(1, count)


def main() -> None:
    words: list[str] = extract_words(SENTENCE)
    total: int = 0
    print(f"Sentence: {SENTENCE}")
    print(f"{'Word':<16}{'Syllables':>9}")
    print("-" * 25)
    for word in words:
        syllables: int = estimate_syllables(word)
        total += syllables
        print(f"{word:<16}{syllables:>9}")
    print("-" * 25)
    print(f"{'Total':<16}{total:>9}")


if __name__ == "__main__":
    main()
