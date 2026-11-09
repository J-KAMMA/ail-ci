import re
import sys

MAX = 9223372036854775807

PAT = re.compile(
    rb'([0-9]+)\.([0-9]+)\.([0-9]+)'
    rb'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
    rb'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
)


def num_ok(b):
    return int(b.decode('ascii')) <= MAX


def parse(line):
    m = PAT.fullmatch(line)
    if not m:
        return None
    ma, mi, pa, pre, build = m.groups()
    if not (num_ok(ma) and num_ok(mi) and num_ok(pa)):
        return None
    pre_key = ()
    if pre is not None:
        keys = []
        for ident in pre.split(b'.'):
            if ident.isdigit():
                if not num_ok(ident):
                    return None
                keys.append((0, int(ident.decode('ascii'))))
            else:
                keys.append((1, ident))
        pre_key = tuple(keys)
    if build is not None:
        for ident in build.split(b'.'):
            if ident.isdigit() and not num_ok(ident):
                return None
    # Release versions (no prerelease) get flag True so they sort higher.
    return (int(ma), int(mi), int(pa), pre is None, pre_key)


def main():
    data = sys.stdin.buffer.read()
    bad = 0
    accepted = []
    for raw in data.split(b'\n'):
        line = raw[:-1] if raw.endswith(b'\r') else raw
        if line == b'':
            continue
        key = parse(line)
        if key is None:
            bad += 1
        else:
            accepted.append((key, line))
    accepted.sort(key=lambda item: (item[0], item[1]))
    out = [f"bad {bad} sorted {len(accepted)}\n".encode('ascii')]
    for _, line in accepted:
        out.append(line + b'\n')
    sys.stdout.buffer.write(b''.join(out))
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == '__main__':
    main()
