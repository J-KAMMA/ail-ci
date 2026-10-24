# task: Write a script that identifies which letters of the alphabet are missing from a hardcoded pangram-candidate sentence using set difference.
import string


SENTENCE: str = "The quick brown fox jumps over the lazy dog"
# Replace with a pangram candidate to test other sentences, e.g.:
# "Pack my box with five dozen liquor jugs" (pangram)
# "A quick movement of the enemy will jeopardize six gunboats" (pangram)


def letters_in(text: str) -> set[str]:
    """Return the set of lowercase ASCII letters appearing in text."""
    return {ch for ch in text.lower() if ch in string.ascii_lowercase}


def missing_letters(text: str) -> list[str]:
    """Return the alphabet letters absent from text, in alphabetical order."""
    alphabet: set[str] = set(string.ascii_lowercase)
    missing: set[str] = alphabet - letters_in(text)
    return sorted(missing)


def main() -> None:
    missing: list[str] = missing_letters(SENTENCE)
    print(f"Sentence: {SENTENCE!r}")
    if missing:
        print(f"Missing letters ({len(missing)}): {', '.join(missing)}")
    else:
        print("The sentence is a pangram: no letters are missing.")


if __name__ == "__main__":
    main()
