# task: Write a script that collapses repeated whitespace in a hardcoded multi-line string into single spaces and strips leading and trailing spaces from each line.
import re


SAMPLE_TEXT: str = """\
   The   quick\t\tbrown   fox   
	jumps    over the
      lazy     dog.   \t
        Repeated    spaces     everywhere      here.
   
Last   line   with    trailing     spaces     """


def normalize_line(line: str) -> str:
    """Collapse runs of whitespace into single spaces and strip edge spaces."""
    collapsed: str = re.sub(r"\s+", " ", line)
    return collapsed.strip(" ")


def normalize_text(text: str) -> list[str]:
    """Normalize every line of the given multi-line text."""
    return [normalize_line(line) for line in text.splitlines()]


def main() -> None:
    for normalized in normalize_text(SAMPLE_TEXT):
        print(f"[{normalized}]")


if __name__ == "__main__":
    main()
