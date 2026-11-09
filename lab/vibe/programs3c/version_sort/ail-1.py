import sys

LIM = "9223372036854775807"
ALNUM = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
DIG = set("0123456789")


def all_in(s, allowed):
    if s == "":
        return False
    for c in s:
        if c not in allowed:
            return False
    return True


def normnum(s):
    # s is a non-empty run of ASCII digits; returns normalized digits or None if out of range
    t = s.lstrip("0")
    if t == "":
        t = "0"
    if len(t) > 19 or (len(t) == 19 and t > LIM):
        return None
    return t


def ids_ok(s):
    for part in s.split("."):
        if not all_in(part, ALNUM):
            return False
        if all_in(part, DIG) and normnum(part) is None:
            return False
    return True


def parse(line):
    plus = line.find("+")
    if plus >= 0:
        head = line[:plus]
        build = line[plus + 1:]
        if not ids_ok(build):
            return None
    else:
        head = line

    dash = head.find("-")
    if dash >= 0:
        core = head[:dash]
        pre = head[dash + 1:]
        if not ids_ok(pre):
            return None
        pre_ids = pre.split(".")
    else:
        core = head
        pre_ids = None

    parts = core.split(".")
    if len(parts) != 3:
        return None
    nums = []
    for p in parts:
        if not all_in(p, DIG):
            return None
        n = normnum(p)
        if n is None:
            return None
        nums.append((len(n), n))

    if pre_ids is None:
        rank = 1
        pk = ()
    else:
        rank = 0
        lst = []
        for part in pre_ids:
            if all_in(part, DIG):
                n = normnum(part)
                lst.append((0, len(n), n))
            else:
                lst.append((1, part))
        pk = tuple(lst)

    return (nums[0], nums[1], nums[2], rank, pk, line)


def main():
    data = sys.stdin.buffer.read().decode("latin-1")
    raw_lines = data.split("\n")
    bad = 0
    keys = []
    for raw in raw_lines:
        if raw.endswith("\r"):
            line = raw[:-1]
        else:
            line = raw
        if line == "":
            continue
        key = parse(line)
        if key is None:
            bad += 1
            continue
        keys.append(key)

    keys.sort()
    out = ["bad " + str(bad) + " sorted " + str(len(keys)) + "\n"]
    for k in keys:
        out.append(k[-1] + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)


main()
