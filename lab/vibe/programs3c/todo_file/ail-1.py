import sys


def parse_id(s):
    if s is None or len(s) == 0:
        return None
    for c in s:
        if c < "0" or c > "9":
            return None
    t = s.lstrip("0")
    if t == "":
        return None
    if len(t) > 10:
        return None
    v = int(t)
    if v < 1 or v > 2147483647:
        return None
    return v


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read().decode("utf-8")

    items = {}  # id -> [text, done]
    errors = 0
    out = []

    for line in data.split("\n"):
        if line == "":
            continue

        idx = line.find(" ")
        if idx < 0:
            cmd = line
            rest = None
        else:
            cmd = line[:idx]
            rest = line[idx + 1:]

        op = cmd if cmd != "" else "error"

        if cmd == "add":
            v = None
            text = ""
            ok = False
            if rest is not None:
                j = rest.find(" ")
                if j >= 0:
                    v = parse_id(rest[:j])
                    text = rest[j + 1:]
                    if v is not None and text != "":
                        ok = True
            if not ok:
                errors += 1
                out.append("error " + op + "\n")
            elif v in items:
                errors += 1
                out.append("error " + op + "\n")
            else:
                items[v] = [text, False]
                out.append("added %d\n" % v)

        elif cmd == "done" or cmd == "remove" or cmd == "show":
            v = parse_id(rest) if rest is not None else None
            if v is None or v not in items:
                errors += 1
                out.append("error " + op + "\n")
            elif cmd == "done":
                if items[v][1]:
                    errors += 1
                    out.append("error " + op + "\n")
                else:
                    items[v][1] = True
                    out.append("done %d\n" % v)
            elif cmd == "remove":
                del items[v]
                out.append("removed %d\n" % v)
            else:
                st = "done" if items[v][1] else "open"
                out.append("todo %d %s %s\n" % (v, st, items[v][0]))

        elif cmd == "list":
            if rest is not None:
                errors += 1
                out.append("error " + op + "\n")
            else:
                open_ids = sorted(k for k in items if not items[k][1])
                out.append("list %d\n" % len(open_ids))
                for k in open_ids:
                    out.append("todo %d open %s\n" % (k, items[k][0]))

        elif cmd == "stats":
            if rest is not None:
                errors += 1
                out.append("error " + op + "\n")
            else:
                total = len(items)
                openc = 0
                chars = 0
                for k in items:
                    rec = items[k]
                    if not rec[1]:
                        openc += 1
                    chars += len(rec[0])
                donec = total - openc
                out.append("stats total %d open %d done %d chars %d errors %d\n"
                           % (total, openc, donec, chars, errors))

        else:
            errors += 1
            out.append("error " + op + "\n")

    sys.stdout.buffer.write("".join(out).encode("utf-8"))
    sys.stdout.flush()


main()
