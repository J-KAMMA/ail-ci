import re
import sys
from collections import Counter

def main() -> None:
    data = sys.stdin.buffer.read()
    words = re.findall(rb"[A-Za-z]+", data)

    counts = Counter(word.lower() for word in words)
    total = len(words)
    unique = len(counts)

    out = sys.stdout.buffer
    out.write(f"words {total} unique {unique}\n".encode("ascii"))

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for word, count in ordered[:20]:
        out.write(word + b" " + str(count).encode("ascii") + b"\n")

if __name__ == "__main__":
    main()
