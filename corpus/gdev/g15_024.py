# task: Attach explanatory notes to a raised ZeroDivisionError with add_note and print the exception along with its notes.
from __future__ import annotations

import traceback


def divide(numerator: float, denominator: float) -> float:
    """Divide two numbers, annotating any ZeroDivisionError with notes."""
    try:
        return numerator / denominator
    except ZeroDivisionError as exc:
        exc.add_note(f"Attempted to divide {numerator!r} by {denominator!r}.")
        exc.add_note("The denominator must be non-zero for this operation.")
        raise


def describe_exception(exc: BaseException) -> str:
    """Return the exception's type, message, and notes as a readable string."""
    lines: list[str] = [f"{type(exc).__name__}: {exc}"]
    notes = getattr(exc, "__notes__", [])
    for index, note in enumerate(notes, start=1):
        lines.append(f"  note {index}: {note}")
    return "\n".join(lines)


def main() -> None:
    try:
        divide(10, 2)
        result = divide(7, 0)
        print(f"Unexpected result: {result}")
    except ZeroDivisionError as exc:
        print("Caught exception with notes:")
        print(describe_exception(exc))
        print()
        print("Formatted traceback (last lines):")
        formatted = traceback.format_exception(exc)
        for line in formatted[-1:]:
            print(line.rstrip())
        print()
        print(f"Raw __notes__ list: {exc.__notes__!r}")


if __name__ == "__main__":
    main()
