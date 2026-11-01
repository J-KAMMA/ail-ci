# task: Write a script that escapes HTML special characters in a hardcoded string using the html module and prints the escaped result.
import html


def main() -> None:
    raw: str = '<script>alert("Hello & welcome, \'friends\'!");</script>'
    escaped: str = html.escape(raw, quote=True)
    print(escaped)


if __name__ == "__main__":
    main()
