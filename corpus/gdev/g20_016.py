# task: Write a script that uses re.subn to count and replace all occurrences of a profanity list in a hardcoded sentence with asterisks and prints the replacement count.
import re

PROFANITY: tuple[str, ...] = ("darn", "heck", "crap", "dang", "shoot")

SENTENCE: str = "Well, darn it, that was a crap shot, and the heck with it, Dang!"


def build_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    # Longer words first so the regex prefers the longest match; sorted() is stable,
    # so the result is deterministic.
    ordered = sorted(words, key=len, reverse=True)
    alternatives = "|".join(re.escape(word) for word in ordered)
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def mask(match: re.Match[str]) -> str:
    return "*" * len(match.group(0))


def main() -> None:
    pattern = build_pattern(PROFANITY)
    censored, count = pattern.subn(mask, SENTENCE)
    print(f"Original: {SENTENCE}")
    print(f"Censored: {censored}")
    print(f"Replacements: {count}")


if __name__ == "__main__":
    main()
