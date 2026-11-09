"""Reference implementation of todo_file (see spec.md): reference.py FILE"""
import sys

MAXID = 2147483647


def parse_id(s):
    if not s or any(c < '0' or c > '9' for c in s):
        return None
    v = int(s)
    return v if 1 <= v <= MAXID else None


def main(argv):
    if len(argv) < 2:
        return 1
    try:
        with open(argv[1], 'rb') as f:
            text = f.read().decode('utf8')
    except (OSError, UnicodeDecodeError):
        return 1
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    items = {}          # id -> [text, done]
    errors = 0
    out = []

    def reject(op):
        nonlocal errors
        errors += 1
        out.append('error %s' % op)

    for line in lines:
        if line == '':
            continue
        sp1 = line.find(' ')
        cmd = line if sp1 < 0 else line[:sp1]
        if cmd == 'list' and sp1 < 0:
            ids = sorted(i for i, v in items.items() if not v[1])
            out.append('list %d' % len(ids))
            for i in ids:
                out.append('todo %d open %s' % (i, items[i][0]))
            continue
        if cmd == 'stats' and sp1 < 0:
            openn = sum(1 for v in items.values() if not v[1])
            chars = sum(len(v[0]) for v in items.values())
            out.append('stats total %d open %d done %d chars %d errors %d' % (
                len(items), openn, len(items) - openn, chars, errors))
            continue
        if sp1 < 0:
            reject(cmd)
            continue
        rest = line[sp1 + 1:]
        if cmd == 'add':
            sp2 = rest.find(' ')
            if sp2 < 0:
                reject('add')
                continue
            ident = parse_id(rest[:sp2])
            body = rest[sp2 + 1:]
            if ident is None or body == '' or ident in items:
                reject('add')
                continue
            items[ident] = [body, False]
            out.append('added %d' % ident)
        elif cmd in ('done', 'remove', 'show'):
            if ' ' in rest:
                reject(cmd)
                continue
            ident = parse_id(rest)
            if ident is None or ident not in items:
                reject(cmd)
                continue
            if cmd == 'done':
                if items[ident][1]:
                    reject('done')
                    continue
                items[ident][1] = True
                out.append('done %d' % ident)
            elif cmd == 'remove':
                del items[ident]
                out.append('removed %d' % ident)
            else:
                out.append('todo %d %s %s' % (ident, 'done' if items[ident][1] else 'open', items[ident][0]))
        else:
            reject(cmd)
    sys.stdout.write(''.join(x + '\n' for x in out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
