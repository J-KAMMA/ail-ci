import sys


def main():
    data = sys.stdin.buffer.read()
    counts = {}
    current = []
    for byte in data:
        if 65 <= byte <= 90:
            current.append(byte + 32)
        elif 97 <= byte <= 122:
            current.append(byte)
        else:
            if current:
                word = bytes(current).decode('ascii')
                counts[word] = counts.get(word, 0) + 1
                current = []
    if current:
        word = bytes(current).decode('ascii')
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    parts = []
    for word, count in ranked[:20]:
        parts.append('%d %s\n' % (count, word))
    sys.stdout.write(''.join(parts))


main()
