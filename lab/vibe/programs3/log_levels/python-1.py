import sys

def main():
    data = sys.stdin.read()
    lines = data.split('\n')
    levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    counts = {l: 0 for l in levels}
    chars = {l: 0 for l in levels}
    longest = {l: 0 for l in levels}
    good = 0
    bad = 0

    for line in lines:
        if line.endswith('\r'):
            line = line[:-1]
        if line == '':
            continue

        if not line.startswith('['):
            bad += 1
            continue

        idx = line.find(']')
        if idx == -1:
            bad += 1
            continue

        level = line[1:idx]
        if level not in counts:
            bad += 1
            continue

        rest = line[idx + 1:]
        if rest == '':
            message = ''
        elif rest[0] == ' ':
            message = rest[1:]
        else:
            bad += 1
            continue

        good += 1
        counts[level] += 1
        length = len(message)
        chars[level] += length
        if length > longest[level]:
            longest[level] = length

    out = []
    out.append(f"lines {good} bad {bad}")
    for l in levels:
        out.append(f"level {l} count {counts[l]} chars {chars[l]} longest {longest[l]}")
    sys.stdout.write('\n'.join(out) + '\n')

if __name__ == '__main__':
    main()
