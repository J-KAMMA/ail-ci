import sys


def main() -> None:
    text: str = sys.stdin.read()
    raw_lines: list[str] = text.split("\n")
    # A trailing newline produces a spurious empty final element; drop it.
    if raw_lines and raw_lines[-1] == "":
        raw_lines.pop()
    lines: list[str] = [line[:-1] if line.endswith("\r") else line for line in raw_lines]

    longest_no: int = 0
    longest_text: str = ""
    longest_len: int = -1

    shortest_no: int = 0
    shortest_text: str = ""
    shortest_len: int = -1

    for index, line in enumerate(lines, start=1):
        length: int = len(line)
        if length > longest_len:
            longest_len = length
            longest_no = index
            longest_text = line
        if length > 0 and (shortest_len < 0 or length < shortest_len):
            shortest_len = length
            shortest_no = index
            shortest_text = line

    if longest_len >= 0:
        print(f"longest: {longest_no} {longest_text}")
    if shortest_len >= 0:
        print(f"shortest: {shortest_no} {shortest_text}")


if __name__ == "__main__":
    main()
