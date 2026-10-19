import sys


def main() -> None:
    out_lines: list[str] = []
    for line in sys.stdin:
        parts = line.split()
        if len(parts) < 2:
            continue
        a, b = parts[0], parts[1]
        if sorted(a) == sorted(b):
            out_lines.append("anagram")
        else:
            out_lines.append("not anagram")
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
