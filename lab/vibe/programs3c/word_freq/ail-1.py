import sys


def flush(cur, counts):
    w = "".join(cur)
    counts[w] = counts.get(w, 0) + 1


def main():
    data = sys.stdin.buffer.read()
    counts = {}
    total = 0
    cur = []
    for b in data:
        if 65 <= b <= 90:
            cur.append(chr(b + 32))
        elif 97 <= b <= 122:
            cur.append(chr(b))
        else:
            if cur:
                flush(cur, counts)
                total += 1
                cur = []
    if cur:
        flush(cur, counts)
        total += 1
        cur = []

    unique = len(counts)
    out = []
    out.append("words " + str(total) + " unique " + str(unique) + "\n")
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for i in range(min(20, len(items))):
        w, c = items[i]
        out.append(w + " " + str(c) + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)


main()
