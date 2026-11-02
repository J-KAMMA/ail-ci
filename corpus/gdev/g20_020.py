# task: Write a script that uses re.findall to pull all URLs starting with http or https from a hardcoded HTML document and prints the unique domains.
import re
from urllib.parse import urlsplit

HTML_DOCUMENT: str = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sample Links Page</title>
  <link rel="stylesheet" href="https://cdn.example-styles.net/css/main.css">
  <script src="http://Scripts.Example.org/js/app.js"></script>
</head>
<body>
  <h1>Useful Resources</h1>
  <p>Visit <a href="https://www.python.org/doc/">Python docs</a> or
     the <a href="https://docs.python.org/3/library/re.html">re module</a>.</p>
  <p>Mirror: <a href="http://www.python.org/downloads/">downloads</a></p>
  <img src="https://images.example.org/logo.png" alt="logo">
  <p>Legacy: <a href="http://legacy.example.com:8080/index.html">legacy</a>
     and <a href="https://user:secret@private.example.com/area">private</a>.</p>
  <p>Plain text mention: https://news.example.net/story?id=42, end.</p>
  <p>Not a URL: ftp://files.example.io/pub and mailto:someone@example.com</p>
  <p>Repeat: <a href="https://CDN.EXAMPLE-STYLES.NET/js/extra.js">cdn</a></p>
</body>
</html>
"""

URL_PATTERN: re.Pattern[str] = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)


def extract_urls(html: str) -> list[str]:
    """Return every http/https URL found in the given HTML text."""
    return URL_PATTERN.findall(html)


def extract_domain(url: str) -> str | None:
    """Return the lowercased hostname of a URL, or None if it has none."""
    hostname: str | None = urlsplit(url).hostname
    if hostname is None:
        return None
    return hostname.lower()


def unique_domains(urls: list[str]) -> list[str]:
    """Return the sorted, de-duplicated list of domains from the URLs."""
    domains: set[str] = set()
    for url in urls:
        domain: str | None = extract_domain(url)
        if domain:
            domains.add(domain)
    return sorted(domains)


def main() -> None:
    urls: list[str] = extract_urls(HTML_DOCUMENT)
    domains: list[str] = unique_domains(urls)

    print(f"URLs found: {len(urls)}")
    print(f"Unique domains: {len(domains)}")
    for domain in domains:
        print(domain)


if __name__ == "__main__":
    main()
