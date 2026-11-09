# task: Write a script that justifies a hardcoded paragraph to 60 characters by distributing extra spaces evenly between words.
"""Justify a hardcoded paragraph to a fixed width by distributing extra spaces evenly."""

from __future__ import annotations

PARAGRAPH: str = (
    "The quick brown fox jumps over the lazy dog while the curious cat watches from "
    "a quiet windowsill, thinking about mice, sunlight, and the long afternoon ahead. "
    "Every so often a bird lands nearby, and the cat twitches its tail with great "
    "interest before settling back into a patient, motionless calm."
)

WIDTH: int = 60


def wrap_words(words: list[str], width: int) -> list[list[str]]:
    """Greedily group words into lines no longer than width characters."""
    lines: list[list[str]] = []
    current: list[str] = []
    length = 0
    for word in words:
        if len(word) > width:
            raise ValueError(f"word longer than line width: {word!r}")
        needed = len(word) if not current else length + 1 + len(word)
        if needed <= width:
            current.append(word)
            length = needed
        else:
            lines.append(current)
            current = [word]
            length = len(word)
    if current:
        lines.append(current)
    return lines


def justify_line(words: list[str], width: int) -> str:
    """Pad a line of words to exactly width characters, spreading spaces evenly.

    Any remainder spaces go to the leftmost gaps, one extra each.
    A single-word line is simply padded on the right.
    """
    if len(words) == 1:
        return words[0].ljust(width)

    letters = sum(len(word) for word in words)
    gaps = len(words) - 1
    total_spaces = width - letters
    base, extra = divmod(total_spaces, gaps)

    parts: list[str] = []
    for index, word in enumerate(words[:-1]):
        parts.append(word)
        parts.append(" " * (base + (1 if index < extra else 0)))
    parts.append(words[-1])
    return "".join(parts)


def main() -> None:
    words = PARAGRAPH.split()
    lines = wrap_words(words, WIDTH)

    for line_number, line in enumerate(lines, start=1):
        is_last = line_number == len(lines)
        if is_last:
            # The final line of a paragraph is conventionally left-aligned, not stretched.
            print(" ".join(line))
        else:
            justified = justify_line(line, WIDTH)
            if len(justified) != WIDTH:
                raise RuntimeError(
                    f"line {line_number} has length {len(justified)}, expected {WIDTH}"
                )
            print(justified)


if __name__ == "__main__":
    main()
