import sys


def main():
    data = sys.stdin.buffer.read().decode('utf-8')
    bad = 0
    sections = {}
    cur = ""

    for raw in data.split('\n'):
        line = raw
        if line.endswith('\r'):
            line = line[:-1]
        line = line.strip(' \t')

        if line == '':
            continue
        if line[0] in '#;':
            continue

        if line[0] == '[':
            if line.endswith(']'):
                cur = line[1:-1]
                sections.setdefault(cur, {})
            else:
                bad += 1
            continue

        if '=' not in line:
            bad += 1
            continue

        k, v = line.split('=', 1)
        k = k.strip(' \t')
        v = v.strip(' \t')
        if k == '' or ' ' in k or '\t' in k:
            bad += 1
            continue

        sections.setdefault(cur, {})[k] = v

    out = ["bad %d\n" % bad]
    for name in sorted(sections):
        out.append("[%s]\n" % name)
        keys = sections[name]
        for k in sorted(keys):
            out.append("%s=%s\n" % (k, keys[k]))

    sys.stdout.buffer.write("".join(out).encode('utf-8'))
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
