import re
import sys
from collections import Counter


def main():
    data = sys.stdin.buffer.read()
    words = [w.lower() for w in re.findall(rb"[A-Za-z]+", data)]
    total = len(words)
    counts = Counter(words)

    out = [f"words {total} unique {len(counts)}"]
    if total > 0:
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        for w, c in items:
            out.append(f"{w.decode('ascii')} {c}")

    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
