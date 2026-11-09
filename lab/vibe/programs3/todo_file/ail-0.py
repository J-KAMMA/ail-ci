import sys


def parse_id(s):
    if s == "":
        return None
    for ch in s:
        if ch < "0" or ch > "9":
            return None
    t = s.lstrip("0")
    if t == "":
        return None
    if len(t) > 10:
        return None
    if len(t) == 10 and t > "2147483647":
        return None
    n = 0
    for ch in t:
        n = n * 10 + (ord(ch) - 48)
    return n


def main():
    if len(sys.argv) < 2:
        return

    with open(sys.argv[1], "r", encoding="utf-8", newline="") as f:
        data = f.read()

    items = {}
    errors = 0
    out = []

    for line in data.split("\n"):
        if line == "":
            continue

        parts = line.split(" ", 2)
        op = parts[0]

        if op == "":
            errors += 1
            out.append("error error\n")
        elif op == "add":
            if len(parts) != 3:
                errors += 1
                out.append("error add\n")
                continue
            ident = parse_id(parts[1])
            text = parts[2]
            if ident is None or text == "":
                errors += 1
                out.append("error add\n")
            elif ident in items:
                errors += 1
                out.append("error add\n")
            else:
                items[ident] = [0, text]
                out.append("added " + str(ident) + "\n")
        elif op == "done":
            if len(parts) != 2:
                errors += 1
                out.append("error done\n")
                continue
            ident = parse_id(parts[1])
            if ident is None or ident not in items:
                errors += 1
                out.append("error done\n")
            elif items[ident][0] == 1:
                errors += 1
                out.append("error done\n")
            else:
                items[ident][0] = 1
                out.append("done " + str(ident) + "\n")
        elif op == "remove":
            if len(parts) != 2:
                errors += 1
                out.append("error remove\n")
                continue
            ident = parse_id(parts[1])
            if ident is None or ident not in items:
                errors += 1
                out.append("error remove\n")
            else:
                del items[ident]
                out.append("removed " + str(ident) + "\n")
        elif op == "show":
            if len(parts) != 2:
                errors += 1
                out.append("error show\n")
                continue
            ident = parse_id(parts[1])
            if ident is None or ident not in items:
                errors += 1
                out.append("error show\n")
            else:
                status = "done" if items[ident][0] == 1 else "open"
                out.append(
                    "todo " + str(ident) + " " + status + " " + items[ident][1] + "\n"
                )
        elif op == "list":
            if len(parts) != 1:
                errors += 1
                out.append("error list\n")
                continue
            open_ids = []
            for ident in sorted(items.keys()):
                if items[ident][0] == 0:
                    open_ids.append(ident)
            out.append("list " + str(len(open_ids)) + "\n")
            for ident in open_ids:
                out.append("todo " + str(ident) + " open " + items[ident][1] + "\n")
        elif op == "stats":
            if len(parts) != 1:
                errors += 1
                out.append("error stats\n")
                continue
            total = len(items)
            opened = 0
            done = 0
            chars = 0
            for ident in items:
                if items[ident][0] == 0:
                    opened += 1
                else:
                    done += 1
                chars += len(items[ident][1])
            out.append(
                "stats total "
                + str(total)
                + " open "
                + str(opened)
                + " done "
                + str(done)
                + " chars "
                + str(chars)
                + " errors "
                + str(errors)
                + "\n"
            )
        else:
            errors += 1
            out.append("error " + op + "\n")

    sys.stdout.write("".join(out))


main()
