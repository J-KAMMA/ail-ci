import re
import sys
from collections import Counter


def main():
    data = sys.stdin.buffer.read()
    words = [w.lower() for w in re.findall(rb"[A-Za-z]+", data)]
    total = len(words)
    counts = Counter(words)
    unique = len(counts)

    out = [f"words {total} unique {unique}\n"]
    if total > 0:
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        for word, count in ordered[:20]:
            out.append(f"{word.decode('ascii')} {count}\n")

    sys.stdout.write("".join(out))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
