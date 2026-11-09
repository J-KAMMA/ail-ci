import sys
import json


class Num:
    __slots__ = ('s',)

    def __init__(self, s):
        self.s = s


def parse_int(s):
    return Num(s)


def parse_const(s):
    raise ValueError("bad constant")


def to_int64(s):
    # s is a valid JSON integer literal. Returns the int value,
    # or None if it is outside the signed 64-bit range.
    neg = s.startswith('-')
    d = s[1:] if neg else s
    if len(d) > 19:
        return None
    if len(d) == 19:
        lim = '9223372036854775808' if neg else '9223372036854775807'
        if d > lim:
            return None
        head = int(d[:-1]) * 10
        last = int(d[-1])
        if neg:
            return -head - last
        return head + last
    v = int(d)
    if neg:
        return -v
    return v


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')

    bad = 0
    tag_count = {}
    tag_total = {}
    user_count = {}

    for raw in lines:
        if raw.endswith(b'\r'):
            raw = raw[:-1]
        if raw.strip(b' \t') == b'':
            continue

        try:
            text = raw.decode('utf-8')
            obj = json.loads(text, parse_int=parse_int, parse_constant=parse_const)
        except Exception:
            bad += 1
            continue

        if not isinstance(obj, dict):
            bad += 1
            continue

        if 'user' not in obj:
            bad += 1
            continue
        user = obj['user']
        if not isinstance(user, str):
            bad += 1
            continue

        if 'amount' not in obj:
            bad += 1
            continue
        amt_raw = obj['amount']
        if not isinstance(amt_raw, Num):
            bad += 1
            continue
        amt = to_int64(amt_raw.s)
        if amt is None:
            bad += 1
            continue

        tag = ''
        if 'tag' in obj:
            tag_val = obj['tag']
            if not isinstance(tag_val, str):
                bad += 1
                continue
            tag = tag_val

        if tag in tag_count:
            tag_count[tag] = tag_count[tag] + 1
            tag_total[tag] = tag_total[tag] + amt
        else:
            tag_count[tag] = 1
            tag_total[tag] = amt

        if user in user_count:
            user_count[user] = user_count[user] + 1
        else:
            user_count[user] = 1

    out = []
    out.append("bad " + str(bad) + " tags " + str(len(tag_count)) + " users " + str(len(user_count)))

    for t in sorted(tag_count.keys()):
        out.append("tag " + t + " count " + str(tag_count[t]) + " total " + str(tag_total[t]))

    names = sorted(user_count.keys())
    names.sort(key=lambda k: user_count[k], reverse=True)
    for i in range(min(10, len(names))):
        uname = names[i]
        out.append("user " + uname + " " + str(user_count[uname]))

    s = "\n".join(out) + "\n"
    sys.stdout.buffer.write(s.encode('utf-8', 'replace'))
    sys.stdout.flush()


main()
