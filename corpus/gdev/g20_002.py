# task: Write a script that uses re.sub with a backreference to swap the first and last names in a list of hardcoded 'Last, First' strings and prints the results.
import re


def swap_names(name: str) -> str:
    """Convert 'Last, First' to 'First Last' using a regex backreference."""
    return re.sub(r"^\s*([^,]+?)\s*,\s*(.+?)\s*$", r"\2 \1", name)


def main() -> None:
    names: list[str] = [
        "Lovelace, Ada",
        "Turing, Alan",
        "Hopper, Grace",
        "Knuth, Donald",
        "Dijkstra, Edsger",
        "  Liskov ,   Barbara  ",
    ]

    for original in names:
        swapped = swap_names(original)
        print(f"{original!r} -> {swapped!r}")


if __name__ == "__main__":
    main()
