"""Print the N most frequent words, as count<TAB>word, ties broken by word."""

import re
import sys
from collections import Counter


def main() -> None:
    limit = int(sys.argv[1])
    text = sys.stdin.read()
    matches = re.findall(r"[A-Za-z]+", text)
    words = [word.lower() for word in matches]
    counts: Counter[str] = Counter(words)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for word, count in ordered[:limit]:
        print("%d\t%s" % (count, word))


main()
