# task: Sort a list of filenames by extension and then by a numeric suffix extracted with a regular expression key function.
import re

# Splits a stem into a leading text part and an optional trailing number.
# The lazy base group makes the number capture the final run of digits.
SUFFIX_PATTERN = re.compile(r"^(?P<base>.*?)(?P<num>\d+)?$")

FILENAMES: list[str] = [
    "report10.txt",
    "report2.txt",
    "image1.png",
    "image10.png",
    "image2.png",
    "notes.txt",
    "archive_v3.zip",
    "archive_v12.zip",
    "README",
    "data007.csv",
    "data7.csv",
    "photo-2.JPG",
    "photo-10.jpg",
    "photo-1.jpg",
]


def split_extension(name: str) -> tuple[str, str]:
    """Return (stem, extension) where extension excludes the dot."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        return name, ""
    return stem, ext


def sort_key(name: str) -> tuple[str, str, int, str]:
    """
    Sort key: extension first, then the non-numeric base name,
    then the numeric suffix (missing suffix sorts before any number),
    and finally the full name as a deterministic tie-breaker.
    """
    stem, ext = split_extension(name)
    match = SUFFIX_PATTERN.match(stem)
    if match is None:  # pragma: no cover - the pattern always matches
        base, num_text = stem, None
    else:
        base = match.group("base")
        num_text = match.group("num")
    number = int(num_text) if num_text is not None else -1
    return (ext.lower(), base.lower(), number, name)


def main() -> None:
    ordered = sorted(FILENAMES, key=sort_key)
    print("Sorted filenames (extension, base name, numeric suffix):")
    for name in ordered:
        ext_text = split_extension(name)[1] or "(none)"
        print(f"  {ext_text:>6}  {name}")


if __name__ == "__main__":
    main()
