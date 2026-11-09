import sys


def main():
    data = sys.stdin.buffer.read().decode('utf-8')
    lines = data.split('\n')
    sections = {}
    bad = 0
    cur = ''

    for raw in lines:
        if raw.endswith('\r'):
            raw = raw[:-1]
        line = raw.strip(' \t')
        if line == '':
            continue
        c = line[0]
        if c == '#' or c == ';':
            continue
        if c == '[':
            if len(line) < 2 or not line.endswith(']'):
                bad += 1
                continue
            name = line[1:-1]
            cur = name
            if name not in sections:
                sections[name] = {}
            continue
        idx = line.find('=')
        if idx < 0:
            bad += 1
            continue
        key = line[:idx].strip(' \t')
        val = line[idx + 1:].strip(' \t')
        if key == '' or ' ' in key or '\t' in key:
            bad += 1
            continue
        if cur not in sections:
            sections[cur] = {}
        sections[cur][key] = val

    out = ['bad ' + str(bad) + '\n']
    for name in sorted(sections.keys()):
        keys = sections[name]
        out.append('[' + name + ']\n')
        for k in sorted(keys.keys()):
            out.append(k + '=' + keys[k] + '\n')

    sys.stdout.buffer.write(''.join(out).encode('utf-8'))


main()
