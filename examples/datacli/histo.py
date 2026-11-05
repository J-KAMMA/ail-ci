"""histo -- print an equal-width histogram of numbers read from standard input.

Usage: histo.py BINS

One number (int or float) per line; blank lines are skipped.  A line that does
not parse as a float is counted and reported on stderr as "skipped N".  BINS
equal-width bins are printed from the smallest to the largest value as
"%12.4f %12.4f %8d  <bar>", the bar scaled to at most 40 characters.
"""

import sys


def parse_values(text: str) -> tuple[list[float], int]:
    values: list[float] = []
    skipped: int = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            values.append(float(line))
        except ValueError:
            skipped += 1
    return values, skipped


def make_bar(count: int, peak: int) -> str:
    if peak <= 0:
        return ""
    width = int((count * 40 + peak // 2) // peak)
    if width < 0:
        width = 0
    if width > 40:
        width = 40
    return "#" * width


def main() -> int:
    args: list[str] = sys.argv[1:]
    if len(args) < 1:
        sys.stderr.write("usage: histo.py BINS\n")
        return 2
    bins = int(args[0])
    if bins <= 0:
        sys.stderr.write("histo.py: BINS must be positive\n")
        return 2
    parsed = parse_values(sys.stdin.read())
    values, skipped = parsed
    if skipped:
        sys.stderr.write("skipped %d\n" % skipped)
    if not values:
        return 0
    low = min(values)
    high = max(values)
    if high == low:
        width = 0.0
    else:
        width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        if width == 0.0:
            index = 0
        else:
            index = int((value - low) / width)
            if index < 0:
                index = 0
            if index >= bins:
                index = bins - 1
        counts[index] += 1
    peak = max(counts)
    i = 0
    while i < bins:
        left = low + width * i
        right = low + width * (i + 1)
        line = "%12.4f %12.4f %8d  %s\n" % (left, right, counts[i], make_bar(counts[i], peak))
        sys.stdout.write(line)
        i += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
