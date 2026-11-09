import sys


def parse_id(s):
    if not s or any(c not in "0123456789" for c in s):
        return None
    t = s.lstrip("0")
    if len(t) > 10:
        return None
    v = int(t) if t else 0
    if 1 <= v <= 2147483647:
        return v
    return None


def reject(cmd):
    return ["error " + (cmd if cmd else "error")], True


def handle(line, state, errors):
    parts = line.split(" ", 1)
    cmd = parts[0]
    rest = parts[1] if len(parts) > 1 else None

    if cmd == "":
        return reject("")

    if cmd == "add":
        if rest is None or " " not in rest:
            return reject(cmd)
        idtok, txt = rest.split(" ", 1)
        ident = parse_id(idtok)
        if ident is None or txt == "":
            return reject(cmd)
        if ident in state:
            return reject(cmd)
        state[ident] = [txt, False]
        return ["added %d" % ident], False

    if cmd in ("done", "remove", "show"):
        if rest is None or " " in rest:
            return reject(cmd)
        ident = parse_id(rest)
        if ident is None or ident not in state:
            return reject(cmd)
        item = state[ident]
        if cmd == "done":
            if item[1]:
                return reject(cmd)
            item[1] = True
            return ["done %d" % ident], False
        if cmd == "remove":
            del state[ident]
            return ["removed %d" % ident], False
        status = "done" if item[1] else "open"
        return ["todo %d %s %s" % (ident, status, item[0])], False

    if cmd == "list":
        if rest is not None:
            return reject(cmd)
        opens = sorted(k for k, v in state.items() if not v[1])
        out = ["list %d" % len(opens)]
        for k in opens:
            out.append("todo %d open %s" % (k, state[k][0]))
        return out, False

    if cmd == "stats":
        if rest is not None:
            return reject(cmd)
        total = len(state)
        done = sum(1 for v in state.values() if v[1])
        open_count = total - done
        chars = sum(len(v[0]) for v in state.values())
        return [
            "stats total %d open %d done %d chars %d errors %d"
            % (total, open_count, done, chars, errors)
        ], False

    return reject(cmd)


def main():
    data = None
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], "rb") as f:
                data = f.read()
        except OSError:
            data = None
    if data is None:
        data = sys.stdin.buffer.read()

    text = data.decode("utf-8", errors="surrogateescape")
    state = {}
    errors = 0
    out = []

    for raw in text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        if line == "":
            continue
        result, is_error = handle(line, state, errors)
        if is_error:
            errors += 1
        out.extend(result)

    if out:
        payload = "\n".join(out) + "\n"
        sys.stdout.buffer.write(payload.encode("utf-8", errors="surrogateescape"))
        sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
