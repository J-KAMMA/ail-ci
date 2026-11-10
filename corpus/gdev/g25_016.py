# task: Build a tokenizer state machine that classifies characters of a fixed string as digits, letters, whitespace, or other and prints the token list.
from dataclasses import dataclass
from enum import Enum, auto


class CharClass(Enum):
    DIGIT = auto()
    LETTER = auto()
    WHITESPACE = auto()
    OTHER = auto()


class State(Enum):
    START = auto()
    DIGITS = auto()
    LETTERS = auto()
    WHITESPACE = auto()
    OTHER = auto()


CLASS_TO_STATE: dict[CharClass, State] = {
    CharClass.DIGIT: State.DIGITS,
    CharClass.LETTER: State.LETTERS,
    CharClass.WHITESPACE: State.WHITESPACE,
    CharClass.OTHER: State.OTHER,
}

SOURCE_TEXT: str = "Item 42 costs $7.50, qty=3;\tdone! x_y\n  ok 0"


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    position: int

    def __str__(self) -> str:
        return f"{self.kind:<10} pos={self.position:<3} text={self.text!r}"


def classify(ch: str) -> CharClass:
    """Classify a single character using ASCII-only rules."""
    if "0" <= ch <= "9":
        return CharClass.DIGIT
    if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return CharClass.LETTER
    if ch in " \t\r\n\f\v":
        return CharClass.WHITESPACE
    return CharClass.OTHER


def tokenize(text: str) -> list[Token]:
    """
    Finite state machine: each character moves the machine to a state
    determined by its class. A token ends when the state changes, or
    always after each OTHER character (those are single-character tokens).
    """
    tokens: list[Token] = []
    buffer: list[str] = []
    current_state: State = State.START
    token_start: int = 0

    def emit() -> None:
        tokens.append(
            Token(
                kind=current_state.name,
                text="".join(buffer),
                position=token_start,
            )
        )
        buffer.clear()

    for index, ch in enumerate(text):
        new_state = CLASS_TO_STATE[classify(ch)]
        if buffer and (new_state is not current_state or new_state is State.OTHER):
            emit()
        if not buffer:
            token_start = index
        buffer.append(ch)
        current_state = new_state

    if buffer:
        emit()

    return tokens


def main() -> None:
    print(f"Source ({len(SOURCE_TEXT)} chars): {SOURCE_TEXT!r}")
    print()
    tokens = tokenize(SOURCE_TEXT)
    for token in tokens:
        print(token)
    print()
    print(f"Total tokens: {len(tokens)}")


if __name__ == "__main__":
    main()
