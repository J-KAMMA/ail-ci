import sys
import re


def main():
    data = sys.stdin.buffer.read()

    total = 0
    counts = {}
    for m in re.finditer(rb"[A-Za-z]+", data):
        total += 1
        w = m.group().lower().decode("ascii")
        counts[w] = counts.get(w, 0) + 1

    out = []
    out.append("words %d unique %d" % (total, len(counts)))

    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for w, c in items[:20]:
        out.append("%s %d" % (w, c))

    sys.stdout.write("\n".join(out) + "\n")


main()
