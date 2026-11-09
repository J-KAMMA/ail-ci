import sys
import re

MAX_ID = 2147483647
_id_re = re.compile(r'[0-9]+')


def parse_id(s):
    if _id_re.fullmatch(s) is None:
        return None
    t = s.lstrip('0')
    if t == '':
        return None
    if len(t) > 10:
        return None
    n = int(t)
    if n < 1 or n > MAX_ID:
        return None
    return n


def main():
    argv = sys.argv[1:]

    data = None
    if argv:
        try:
            with open(argv[0], 'r', encoding='utf-8-sig') as f:
                data = f.read()
        except OSError:
            data = None
    if data is None:
        data = sys.stdin.read()

    out = []
    state = {}
    errors = 0

    for raw in data.split('\n'):
        line = raw[:-1] if raw.endswith('\r') else raw
        if line == '':
            continue

        i = line.find(' ')
        if i == -1:
            name = line
            rest = None
        else:
            name = line[:i]
            rest = line[i + 1:]

        if name == '':
            errors += 1
            out.append('error error')
            continue

        if name == 'add':
            if i == -1:
                errors += 1
                out.append('error add')
                continue
            j = line.find(' ', i + 1)
            if j == -1:
                errors += 1
                out.append('error add')
                continue
            nid = parse_id(line[i + 1:j])
            text = line[j + 1:]
            if nid is None or text == '' or nid in state:
                errors += 1
                out.append('error add')
                continue
            state[nid] = [False, text]
            out.append('added %d' % nid)

        elif name in ('done', 'remove', 'show'):
            nid = parse_id(rest) if rest is not None else None
            if nid is None or nid not in state:
                errors += 1
                out.append('error ' + name)
                continue
            if name == 'done':
                if state[nid][0]:
                    errors += 1
                    out.append('error done')
                    continue
                state[nid][0] = True
                out.append('done %d' % nid)
            elif name == 'remove':
                del state[nid]
                out.append('removed %d' % nid)
            else:
                out.append('todo %d %s %s' % (
                    nid,
                    'done' if state[nid][0] else 'open',
                    state[nid][1],
                ))

        elif name in ('list', 'stats'):
            if rest is not None and rest != '':
                errors += 1
                out.append('error ' + name)
                continue
            if name == 'list':
                ids = sorted(k for k, v in state.items() if not v[0])
                out.append('list %d' % len(ids))
                for k in ids:
                    out.append('todo %d open %s' % (k, state[k][1]))
            else:
                total = len(state)
                open_count = sum(1 for v in state.values() if not v[0])
                done_count = total - open_count
                chars = sum(len(v[1]) for v in state.values())
                out.append('stats total %d open %d done %d chars %d errors %d' % (
                    total, open_count, done_count, chars, errors,
                ))

        else:
            errors += 1
            out.append('error ' + name)

    sys.stdout.write(''.join(l + '\n' for l in out))


if __name__ == '__main__':
    main()
