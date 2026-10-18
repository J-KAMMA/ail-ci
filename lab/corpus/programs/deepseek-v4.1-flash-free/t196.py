import re
import sys

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\d{3}-\d{3}-(\d{4})")


def mask_email(match: re.Match[str]) -> str:
    domain = match.group(0).rsplit("@", 1)[1]
    return "***@" + domain


def mask_phone(match: re.Match[str]) -> str:
    return "XXX-XXX-" + match.group(1)


def main() -> None:
    for line in sys.stdin:
        line = line.rstrip("\n")
        line = EMAIL_RE.sub(mask_email, line)
        line = PHONE_RE.sub(mask_phone, line)
        print(line)


if __name__ == "__main__":
    main()
