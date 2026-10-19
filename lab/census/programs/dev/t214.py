import sys


def unmatched_for_pair(s: str, open_ch: str, close_ch: str) -> int:
    """Return the minimum insertions needed for one bracket type using a counter."""
    balance = 0
    insertions = 0
    for ch in s:
        if ch == open_ch:
            balance += 1
        elif ch == close_ch:
            if balance > 0:
                balance -= 1
            else:
                insertions += 1  # need to insert an opening bracket
    return insertions + balance  # remaining opens need closing brackets


def min_insertions(s: str) -> int:
    """Sum the independent results for (), [] and {}."""
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    return sum(unmatched_for_pair(s, o, c) for o, c in pairs)


def main() -> None:
    data = sys.stdin.read().split("\n")
    if not data or not data[0].strip():
        return
    n = int(data[0].strip())
    out_lines: list[str] = []
    for i in range(n):
        idx = 1 + i
        line = data[idx] if idx < len(data) else ""
        line = line.strip()
        out_lines.append(str(min_insertions(line)))
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
