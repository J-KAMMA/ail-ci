import sys
from collections import Counter


def main():
    data = sys.stdin.buffer.read()

    counts = Counter()
    total = 0
    word = bytearray()

    for b in data:
        if 65 <= b <= 90:          # A-Z
            word.append(b + 32)
        elif 97 <= b <= 122:       # a-z
            word.append(b)
        else:
            if word:
                counts[bytes(word)] += 1
                total += 1
                word.clear()

    if word:
        counts[bytes(word)] += 1
        total += 1

    lines = [f"words {total} unique {len(counts)}"]

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for w, count in ordered[:20]:
        lines.append(f"{w.decode('ascii')} {count}")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
