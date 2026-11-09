import sys

def main():
    data = sys.stdin.buffer.read().decode('utf-8')
    lines = data.split('\n')
    bad = 0
    sections = {}
    cur = ''
    for raw in lines:
        line = raw
        if line.endswith('\r'):
            line = line[:-1]
        line = line.strip(' \t')
        if line == '':
            continue
        c = line[0]
        if c == '#' or c == ';':
            continue
        if c == '[':
            if not line.endswith(']'):
                bad += 1
                continue
            name = line[1:-1]
            cur = name
            if name not in sections:
                sections[name] = {}
            continue
        pos = line.find('=')
        if pos < 0:
            bad += 1
            continue
        key = line[:pos].strip(' \t')
        val = line[pos + 1:].strip(' \t')
        if key == '' or ' ' in key or '\t' in key:
            bad += 1
            continue
        if cur not in sections:
            sections[cur] = {}
        sections[cur][key] = val
    out = ['bad ' + str(bad) + '\n']
    for name in sorted(sections.keys()):
        out.append('[' + name + ']\n')
        d = sections[name]
        for k in sorted(d.keys()):
            out.append(k + '=' + d[k] + '\n')
    sys.stdout.write(''.join(out))

main()
