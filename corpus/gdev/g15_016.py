# task: Validate an email-like string with a regular expression and raise a custom ValidationError that carries the name of the offending field.
import re


class ValidationError(Exception):
    """Raised when a value fails validation; carries the offending field name."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field: str = field
        self.message: str = message


LOCAL_PART = r"[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*"
DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
DOMAIN = rf"(?:{DOMAIN_LABEL}\.)+[A-Za-z]{{2,63}}"
EMAIL_RE: re.Pattern[str] = re.compile(rf"{LOCAL_PART}@{DOMAIN}")

MAX_EMAIL_LENGTH: int = 254


def validate_email(value: object, field: str = "email") -> str:
    """Return the email string if valid, otherwise raise ValidationError."""
    if not isinstance(value, str):
        raise ValidationError(field, "must be a string")
    if not value.strip():
        raise ValidationError(field, "must not be empty")
    if len(value) > MAX_EMAIL_LENGTH:
        raise ValidationError(field, f"must be at most {MAX_EMAIL_LENGTH} characters")
    if EMAIL_RE.fullmatch(value) is None:
        raise ValidationError(field, "is not a valid email address")
    return value


def validate_fields(record: dict[str, object]) -> dict[str, str]:
    """Validate every email field in a record, failing on the first bad one."""
    validated: dict[str, str] = {}
    for field in record:
        validated[field] = validate_email(record[field], field=field)
    return validated


def main() -> None:
    samples: list[dict[str, object]] = [
        {"primary": "alice@example.com"},
        {"primary": "bob.smith+tag@mail.example.co.uk"},
        {"primary": "no-at-sign.example.com"},
        {"primary": "double..dot@example.com"},
        {"primary": ".leading@example.com"},
        {"primary": "user@localhost"},
        {"primary": "   "},
        {"primary": 42},
        {"primary": "ok@example.org", "backup": "bad@@example.org"},
        {"primary": "x" * 250 + "@example.com"},
    ]

    for index, record in enumerate(samples, start=1):
        try:
            result = validate_fields(record)
        except ValidationError as exc:
            print(f"[{index}] invalid field {exc.field!r}: {exc.message}")
        else:
            print(f"[{index}] valid: {result}")


if __name__ == "__main__":
    main()
