import re
import sys

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_PATTERN = re.compile(r"\d{3}-\d{3}-(\d{4})")


def mask_line(line: str) -> str:
    masked = EMAIL_PATTERN.sub(r"***\1", line)
    return PHONE_PATTERN.sub(r"XXX-XXX-\1", masked)


def main() -> None:
    for line in sys.stdin:
        print(mask_line(line), end="")


if __name__ == "__main__":
    main()
