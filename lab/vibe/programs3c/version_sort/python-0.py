import re
import sys

MAXV = 9223372036854775807

PAT = re.compile(
    rb'([0-9]+)\.([0-9]+)\.([0-9]+)'
    rb'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    rb'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
)


def to_int(digits):
    s = digits.lstrip(b'0')
    if len(s) > 19:
        return None
    v = int(s.decode('ascii')) if s else 0
    if v > MAXV:
        return None
    return v


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')

    bad = 0
    entries = []

    for raw in lines:
        line = raw[:-1] if raw.endswith(b'\r') else raw
        if line.strip() == b'':
            continue

        m = PAT.fullmatch(line)
        if not m:
            bad += 1
            continue

        major = to_int(m.group(1))
        minor = to_int(m.group(2))
        patch = to_int(m.group(3))
        if major is None or minor is None or patch is None:
            bad += 1
            continue

        pre = m.group(4)
        build = m.group(5)

        ok = True
        if build is not None:
            for ident in build.split(b'.'):
                if ident.isdigit() and to_int(ident) is None:
                    ok = False
                    break
        if not ok:
            bad += 1
            continue

        if pre is None:
            flag = 1
            pk = ()
        else:
            flag = 0
            items = []
            for ident in pre.split(b'.'):
                if ident.isdigit():
                    v = to_int(ident)
                    if v is None:
                        ok = False
                        break
                    items.append((0, v, b''))
                else:
                    items.append((1, 0, ident))
            if not ok:
                bad += 1
                continue
            pk = tuple(items)

        key = (major, minor, patch, flag, pk, line)
        entries.append((key, line))

    entries.sort(key=lambda e: e[0])

    out = [f"bad {bad} sorted {len(entries)}\n".encode('ascii')]
    for _, line in entries:
        out.append(line + b'\n')

    sys.stdout.buffer.write(b''.join(out))
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == '__main__':
    main()
