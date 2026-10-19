import re
import sys

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(?<!\d)\d{3}-\d{3}-(\d{4})(?!\d)")


def mask_email(match: re.Match[str]) -> str:
    return "***@" + match.group(1)


def mask_phone(match: re.Match[str]) -> str:
    return "XXX-XXX-" + match.group(1)


def mask_line(line: str) -> str:
    line = EMAIL_RE.sub(mask_email, line)
    line = PHONE_RE.sub(mask_phone, line)
    return line


def main() -> None:
    for line in sys.stdin:
        print(mask_line(line.rstrip("\n")))


if __name__ == "__main__":
    main()
