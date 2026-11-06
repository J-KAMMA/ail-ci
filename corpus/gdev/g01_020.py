# task: Parse embedded query-string data such as 'a=1&b=2&a=3' with urllib.parse and print each key with its list of values.
from urllib.parse import parse_qs


EMBEDDED_QUERIES: list[str] = [
    "a=1&b=2&a=3",
    "color=red&size=M&color=blue&color=green",
    "empty=&flag&x=%20hello%20world&x=a%2Bb",
]


def group_query(query: str) -> dict[str, list[str]]:
    """Parse a query string and return each key mapped to its list of values."""
    return parse_qs(query, keep_blank_values=True, strict_parsing=False)


def main() -> None:
    for index, query in enumerate(EMBEDDED_QUERIES, start=1):
        print(f"Query {index}: {query!r}")
        grouped = group_query(query)
        for key, values in grouped.items():
            print(f"  {key!r}: {values!r}")
        print()


if __name__ == "__main__":
    main()
