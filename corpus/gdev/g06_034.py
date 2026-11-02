# task: Write a script that finds all anagram groups in a hardcoded list of words by using frozensets of character counts as keys.
from collections import Counter, defaultdict
from typing import Iterable

WORDS: list[str] = [
    "listen", "silent", "enlist", "inlets",
    "google", "gogole", "cat", "act", "tac",
    "dog", "god", "odg", "stone", "tones",
    "notes", "onset", "seton", "banana",
    "apple", "paper", "pepper", "triangle",
    "integral", "relation", "alerting", "altering",
    "night", "thing", "sign", "gins",
    "evil", "vile", "live", "veil", "level",
    "restful", "fluster", "flutters", "hello",
]

CharSignature = frozenset[tuple[str, int]]


def char_signature(word: str) -> CharSignature:
    """Return a hashable signature: the frozenset of (character, count) pairs."""
    return frozenset(Counter(word.lower()).items())


def group_anagrams(words: Iterable[str]) -> dict[CharSignature, list[str]]:
    """Group words by their character-count signature."""
    groups: defaultdict[CharSignature, list[str]] = defaultdict(list)
    for word in words:
        groups[char_signature(word)].append(word)
    return dict(groups)


def find_anagram_groups(words: Iterable[str]) -> list[list[str]]:
    """Return sorted groups (size >= 2) of distinct words that are anagrams of each other."""
    result: list[list[str]] = []
    for members in group_anagrams(words).values():
        unique_sorted = sorted(set(member.lower() for member in members))
        if len(unique_sorted) >= 2:
            result.append(unique_sorted)
    result.sort(key=lambda group: (len(group), group))
    return result


def main() -> None:
    groups = find_anagram_groups(WORDS)
    print(f"Found {len(groups)} anagram group(s) among {len(WORDS)} words:")
    for index, group in enumerate(groups, start=1):
        print(f"{index:>2}. {', '.join(group)}")


if __name__ == "__main__":
    main()
