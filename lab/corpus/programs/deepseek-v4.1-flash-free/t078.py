import sys


def format_codepoint(ch: str) -> str:
    code = ord(ch)
    return f"U+{code:04X} {ch}"


def main() -> None:
    data = sys.stdin.read()
    lines = data.splitlines()
    first = next((line for line in lines if line != ""), "")
    out = "\n".join(format_codepoint(ch) for ch in first)
    if out:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
