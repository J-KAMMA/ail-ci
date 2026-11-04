# task: Use recursion with memoization to count and list all ways to segment the string 'catsanddogs' into dictionary words.
"""Count and list all ways to segment 'catsanddogs' into dictionary words.

Uses recursion with memoization: the segmentations of each suffix are
computed once and cached by starting index.
"""

from typing import Dict, List, Tuple

TEXT: str = "catsanddogs"
DICTIONARY: frozenset[str] = frozenset({"cat", "cats", "and", "sand", "dog", "dogs"})

Segmentation = Tuple[str, ...]


def segment_from(
    text: str,
    words: frozenset[str],
    start: int,
    memo: Dict[int, List[Segmentation]],
) -> List[Segmentation]:
    """Return every segmentation of text[start:] into dictionary words."""
    if start == len(text):
        return [()]
    if start in memo:
        return memo[start]

    results: List[Segmentation] = []
    for end in range(start + 1, len(text) + 1):
        word = text[start:end]
        if word in words:
            for rest in segment_from(text, words, end, memo):
                results.append((word,) + rest)

    memo[start] = results
    return results


def main() -> None:
    memo: Dict[int, List[Segmentation]] = {}
    all_segmentations = segment_from(TEXT, DICTIONARY, 0, memo)
    ordered = sorted(all_segmentations)

    print(f"Text: {TEXT}")
    print(f"Dictionary: {', '.join(sorted(DICTIONARY))}")
    print(f"Number of ways: {len(ordered)}")
    for index, parts in enumerate(ordered, start=1):
        print(f"{index}. {' '.join(parts)}")


if __name__ == "__main__":
    main()
