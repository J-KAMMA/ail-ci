import sys


def main() -> None:
    lines: list[str] = sys.stdin.read().splitlines()
    entries: list[tuple[int, str]] = []
    for line in lines:
        words = line.split()
        if not words:
            continue
        entries.append((len(words), line))

    entries.sort(key=lambda item: (-item[0], item[1].lower()))

    out_lines = [f"{count} {text}" for count, text in entries]
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
