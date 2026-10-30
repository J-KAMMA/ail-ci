"""Reference implementation of ticket_audit (see spec.md): reference.py FILE"""
import re
import sys

SYNTAX = {
    'code': re.compile(rb'[A-Z]{3}'),
    'name': re.compile(rb'[\x21-\x7b\x7d\x7e](?:[\x20-\x7b\x7d\x7e]{0,38}[\x21-\x7b\x7d\x7e])?'),
    'capacity': re.compile(rb'[0-9]{1,6}'),
    'event': re.compile(rb'[0-9]{6}'),
    'date': re.compile(rb'[0-9]{4}-[0-9]{2}-[0-9]{2}'),
    'time': re.compile(rb'[0-9]{2}:[0-9]{2}'),
    'price': re.compile(rb'[0-9]{1,4}\.[0-9]{2}'),
    'seat': re.compile(rb'[A-Z][0-9]{1,3}'),
    'buyer': re.compile(rb'[a-z][a-z0-9]{3,11}'),
    'count': re.compile(rb'[0-9]{1,9}'),
    'cents': re.compile(rb'[0-9]{1,12}'),
}
FIELDS = {
    b'V': ('code', 'name', 'capacity'),
    b'E': ('event', 'code', 'date', 'time', 'price'),
    b'S': ('event', 'seat', 'buyer'),
    b'R': ('event', 'seat'),
    b'END': ('count', 'cents'),
}
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
EXIT = {'header': 2, 'syntax': 3, 'value': 4, 'reference': 5, 'duplicate': 6, 'capacity': 7, 'summary': 8}


def no_lead_zero(f):
    return f == b'0' or not f.startswith(b'0')


def value_ok(kind, f):
    if kind == 'capacity':
        return not f.startswith(b'0') and 1 <= int(f) <= 100000
    if kind == 'event':
        d = [c - 48 for c in f]
        return (3 * (d[0] + d[2] + d[4]) + d[1] + d[3] + d[5]) % 10 == 0
    if kind == 'date':
        y, m, d = int(f[0:4]), int(f[5:7]), int(f[8:10])
        if not (2000 <= y <= 2099 and 1 <= m <= 12):
            return False
        last = 29 if m == 2 and y % 4 == 0 else DAYS[m - 1]
        return 1 <= d <= last
    if kind == 'time':
        return int(f[0:2]) <= 23 and int(f[3:5]) <= 59
    if kind == 'price':
        whole = f[:-3]
        return no_lead_zero(whole) and int(f[-2:]) % 5 == 0
    if kind == 'seat':
        return f[1] != 48
    if kind in ('count', 'cents'):
        return no_lead_zero(f)
    return True


def money(c):
    return '%d.%02d' % (c // 100, c % 100)


def main(argv):
    if len(argv) != 2:
        return 1
    try:
        with open(argv[1], 'rb') as fh:
            data = fh.read()
    except OSError:
        return 1
    lines = data.split(b'\n')
    if data.endswith(b'\n') or data == b'':
        lines.pop()

    def fail(n, cat):
        sys.stdout.write('line %d: %s\n' % (n, cat))
        return EXIT[cat]

    if not lines or lines[0] != b'TKT/1':
        return fail(1, 'header')
    venues = {}      # code -> capacity
    events = {}      # event -> [venue, price cents, sold set]
    records = 0
    revenue = 0
    nsold = nref = 0
    ended = False
    for idx in range(1, len(lines)):
        n = idx + 1
        if ended:
            return fail(n, 'summary')
        parts = lines[idx].split(b'|')
        kinds = FIELDS.get(parts[0])
        if kinds is None or len(parts) != len(kinds) + 1:
            return fail(n, 'syntax')
        fields = parts[1:]
        for kind, f in zip(kinds, fields):
            if not SYNTAX[kind].fullmatch(f):
                return fail(n, 'syntax')
        for kind, f in zip(kinds, fields):
            if not value_ok(kind, f):
                return fail(n, 'value')
        t = parts[0]
        if t == b'V':
            if fields[0] in venues:
                return fail(n, 'duplicate')
            venues[fields[0]] = int(fields[2])
        elif t == b'E':
            if fields[1] not in venues:
                return fail(n, 'reference')
            if fields[0] in events:
                return fail(n, 'duplicate')
            p = fields[4]
            events[fields[0]] = [fields[1], int(p[:-3]) * 100 + int(p[-2:]), set()]
        elif t == b'S':
            ev = events.get(fields[0])
            if ev is None:
                return fail(n, 'reference')
            if fields[1] in ev[2]:
                return fail(n, 'duplicate')
            if len(ev[2]) >= venues[ev[0]]:
                return fail(n, 'capacity')
            ev[2].add(fields[1])
            revenue += ev[1]
            nsold += 1
        elif t == b'R':
            ev = events.get(fields[0])
            if ev is None or fields[1] not in ev[2]:
                return fail(n, 'reference')
            ev[2].remove(fields[1])
            revenue -= ev[1]
            nref += 1
        else:
            if int(fields[0]) != records or int(fields[1]) != revenue:
                return fail(n, 'summary')
            ended = True
            continue
        records += 1
    if not ended:
        return fail(len(lines) + 1, 'summary')
    out = ['venues %d events %d sold %d refunds %d' % (len(venues), len(events), nsold, nref),
           'revenue ' + money(revenue)]
    per = {v: [0, 0, 0] for v in venues}
    for ev in events.values():
        p = per[ev[0]]
        p[0] += 1
        p[1] += len(ev[2])
        p[2] += len(ev[2]) * ev[1]
    for v in sorted(per):
        p = per[v]
        out.append('%s events=%d tickets=%d revenue=%s' % (v.decode(), p[0], p[1], money(p[2])))
    top = sorted(events.items(), key=lambda kv: (-len(kv[1][2]), kv[0]))[:3]
    for e, ev in top:
        out.append('top %s %d' % (e.decode(), len(ev[2])))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
