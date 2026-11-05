import sys


def main() -> int:
    data = sys.stdin.buffer.read()
    counts: dict[str, int] = {}
    word = ""
    i = 0
    while i <= len(data):
        c = 32
        if i < len(data):
            c = data[i]
        if c == 32 or c == 10 or c == 9 or c == 13 or i == len(data):
            if len(word) > 0:
                if word in counts:
                    counts[word] += 1
                else:
                    counts[word] = 1
                word = ""
        else:
            word += chr(c)
        i += 1
    keys: list[str] = []
    for k in counts:
        keys.append(k)
    i = 1
    while i < len(keys):
        j = i
        while j > 0 and keys[j - 1] > keys[j]:
            t = keys[j - 1]
            keys[j - 1] = keys[j]
            keys[j] = t
            j -= 1
        i += 1
    total = 0
    for k in keys:
        total += counts[k]
    print("distinct=%d words=%d" % (len(keys), total))
    for k in keys:
        print("%s %d" % (k, counts[k]))
    return 0


main()
