"""Reference implementation of ini_merge (see spec.md): reference.py < config"""
import sys


def main():
    text = sys.stdin.buffer.read().decode('utf8')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    bad = 0
    section = ''
    sections = {}
    for raw in lines:
        line = raw[:-1] if raw.endswith('\r') else raw
        line = line.strip(' \t')
        if not line or line[0] in '#;':
            continue
        if line[0] == '[':
            if not line.endswith(']'):
                bad += 1
                continue
            section = line[1:-1]
            sections.setdefault(section, {})
            continue
        if '=' not in line:
            bad += 1
            continue
        key, value = line.split('=', 1)
        key = key.strip(' \t')
        value = value.strip(' \t')
        if not key or ' ' in key or '\t' in key:
            bad += 1
            continue
        sections.setdefault(section, {})[key] = value
    out = ['bad %d' % bad]
    for name in sorted(sections):
        out.append('[%s]' % name)
        for key in sorted(sections[name]):
            out.append('%s=%s' % (key, sections[name][key]))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
