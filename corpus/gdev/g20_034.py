# task: Write a script that uses re.sub to replace all runs of whitespace in a hardcoded multi-line text with single spaces while preserving paragraph breaks marked by double newlines.
import re


SAMPLE_TEXT: str = """
  The   quick brown fox
  jumps    over the   lazy dog.\tIt was   a   sunny
  day,   and   everyone   was   happy.



    Second   paragraph   starts   here,
  with   irregular      spacing	and tabs.
  It continues    across   several
      lines   too.

Third paragraph   is   short.   
"""


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace runs into single spaces, keeping paragraph breaks.

    Paragraphs are separated by one or more blank lines (a newline, optional
    whitespace, then another newline). Within each paragraph, every run of
    whitespace becomes a single space. Paragraphs are rejoined with a
    double newline.
    """
    paragraphs: list[str] = re.split(r"\n\s*\n", text)
    cleaned: list[str] = []
    for paragraph in paragraphs:
        collapsed: str = re.sub(r"\s+", " ", paragraph).strip()
        if collapsed:
            cleaned.append(collapsed)
    return "\n\n".join(cleaned)


def main() -> None:
    result: str = normalize_whitespace(SAMPLE_TEXT)
    print(result)


if __name__ == "__main__":
    main()
