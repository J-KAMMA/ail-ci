# task: Write a script that uses re.findall to extract all email-like addresses from a hardcoded multi-line text and prints them sorted and deduplicated.
import re


TEXT: str = """
Contact us at support@example.com for general questions.
For sales, reach out to Sales.Team@Example.COM or sales.team@example.com.
Invalid entries like user@ or @nodomain.org should be ignored.
Billing: billing+invoices@mail.example.co.uk
Engineering lead: jane_doe-42@dev.example.org, backup: jane_doe-42@dev.example.org
Old address: john.smith@old-domain.net; typo: john.smith@@old-domain.net
Press inquiries -> press@news.example.io.
Mixed case duplicate: SUPPORT@example.com
"""

EMAIL_PATTERN: str = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"


def extract_emails(text: str) -> list[str]:
    """Return all email-like addresses found in text, normalized to lowercase."""
    matches: list[str] = re.findall(EMAIL_PATTERN, text)
    return [match.lower() for match in matches]


def main() -> None:
    emails: list[str] = extract_emails(TEXT)
    unique_sorted: list[str] = sorted(set(emails))
    for email in unique_sorted:
        print(email)


if __name__ == "__main__":
    main()
