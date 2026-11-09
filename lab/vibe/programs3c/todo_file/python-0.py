import sys

MAXID = 2147483647
KNOWN = {"add", "done", "remove", "show", "list", "stats"}


def parse_id(s):
    if not s or not s.isascii() or not s.isdigit():
        return None
    t = s.lstrip("0")
    if len(t) > 10:
        return None
    v = int(t) if t else 0
    if 1 <= v <= MAXID:
        return v
    return None


def err_line(cmd):
    return "error" if cmd == "" else "error " + cmd


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            raw = f.read()
    else:
        raw = sys.stdin.buffer.read()
    text = raw.decode("utf-8", "surrogateescape")

    items = {}  # id -> [text, done]
    errors = 0
    out = []

    for line in text.split("\n"):
        if line == "":
            continue
        parts = line.split(" ", 2)
        cmd = parts[0]

        if cmd == "" or cmd not in KNOWN:
            errors += 1
            out.append(err_line(cmd))
            continue

        if cmd == "add":
            if len(parts) != 3 or parts[2] == "":
                errors += 1
                out.append(err_line(cmd))
                continue
            vid = parse_id(parts[1])
            if vid is None or vid in items:
                errors += 1
                out.append(err_line(cmd))
                continue
            items[vid] = [parts[2], False]
            out.append("added %d" % vid)

        elif cmd == "list":
            if len(parts) != 1:
                errors += 1
                out.append(err_line(cmd))
                continue
            opens = sorted(k for k, v in items.items() if not v[1])
            out.append("list %d" % len(opens))
            for k in opens:
                out.append("todo %d open %s" % (k, items[k][0]))

        elif cmd == "stats":
            if len(parts) != 1:
                errors += 1
                out.append(err_line(cmd))
                continue
            total = len(items)
            done_n = sum(1 for v in items.values() if v[1])
            open_n = total - done_n
            chars = sum(len(v[0]) for v in items.values())
            out.append(
                "stats total %d open %d done %d chars %d errors %d"
                % (total, open_n, done_n, chars, errors)
            )

        else:  # done, remove, show
            if len(parts) != 2:
                errors += 1
                out.append(err_line(cmd))
                continue
            vid = parse_id(parts[1])
            if vid is None or vid not in items:
                errors += 1
                out.append(err_line(cmd))
                continue
            if cmd == "done":
                if items[vid][1]:
                    errors += 1
                    out.append(err_line(cmd))
                    continue
                items[vid][1] = True
                out.append("done %d" % vid)
            elif cmd == "remove":
                del items[vid]
                out.append("removed %d" % vid)
            else:  # show
                status = "done" if items[vid][1] else "open"
                out.append("todo %d %s %s" % (vid, status, items[vid][0]))

    data = "".join(s + "\n" for s in out)
    sys.stdout.buffer.write(data.encode("utf-8", "surrogateescape"))
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
