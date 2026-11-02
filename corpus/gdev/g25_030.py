# task: Create a state machine that detects the pattern 'abb' in a fixed input string and prints the index positions where the pattern is completed.
from typing import Final

PATTERN: Final[str] = "abb"
TEXT: Final[str] = "ababbxabbbabb"
ACCEPT_STATE: Final[int] = 3


def next_state(state: int, ch: str) -> int:
    """Transition function of a DFA that recognizes the pattern 'abb'.

    States:
        0 - no useful prefix matched
        1 - matched 'a'
        2 - matched 'ab'
        3 - matched 'abb' (accepting)
    """
    if ch == "a":
        return 1
    if ch == "b":
        if state == 1:
            return 2
        if state == 2:
            return 3
        if state == 3:
            return 0
        return 0
    return 0


def find_completions(text: str) -> list[int]:
    """Run the state machine over text and return indices where the pattern completes."""
    completions: list[int] = []
    state = 0
    for index, ch in enumerate(text):
        state = next_state(state, ch)
        if state == ACCEPT_STATE:
            completions.append(index)
    return completions


def main() -> None:
    print(f"Text: {TEXT}")
    print(f"Pattern: {PATTERN}")
    matches = find_completions(TEXT)
    if not matches:
        print("Pattern not found.")
        return
    for index in matches:
        print(f"Pattern '{PATTERN}' completed at index {index}")
    print(f"Total matches: {len(matches)}")


if __name__ == "__main__":
    main()
