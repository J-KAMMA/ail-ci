import sys


def main():
    data = sys.stdin.buffer.read() + b"\n"
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
                w = ''.join(cur)
                counts[w] = counts.get(w, 0) + 1
                total += 1
                cur = []

    unique = len(counts)
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = ["words " + str(total) + " unique " + str(unique) + "\n"]
    for w, c in items[:20]:
        out.append(w + " " + str(c) + "\n")
    sys.stdout.write(''.join(out))
    sys.exit(0)


main()
