# task: Write a script that uses re.match to check whether hardcoded filenames have a valid image extension (png, jpg, gif) case-insensitively and prints the matching names.
import re
from typing import Final

IMAGE_PATTERN: Final[re.Pattern[str]] = re.compile(r".+\.(?:png|jpg|gif)\Z", re.IGNORECASE)

FILENAMES: Final[tuple[str, ...]] = (
    "photo.png",
    "holiday.JPG",
    "logo.Gif",
    "resume.pdf",
    "archive.tar.gz",
    "banner.jpeg",
    "icon.PNG",
    "notes.txt",
    "diagram.gif",
    "scan.jpg.bak",
    "picture.jpg",
    ".png",
    "README",
)


def is_image_filename(name: str) -> bool:
    """Return True if the filename ends with a valid image extension (case-insensitive)."""
    return re.match(IMAGE_PATTERN, name) is not None


def main() -> None:
    matches: list[str] = [name for name in FILENAMES if is_image_filename(name)]
    print("Image files:")
    for name in matches:
        print(name)
    print(f"Total: {len(matches)}")


if __name__ == "__main__":
    main()
