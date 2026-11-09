"""Reference implementation of jsonl_stats (see spec.md): reference.py < data.jsonl"""
import json
import sys

MINI = -(1 << 63)
MAXI = (1 << 63) - 1


def main():
    data = sys.stdin.buffer.read().decode('utf8')
    bad = 0
    tags = {}
    users = {}
    for raw in data.split('\n'):
        line = raw[:-1] if raw.endswith('\r') else raw
        if not line.strip(' \t'):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(obj, dict):
            bad += 1
            continue
        user = obj.get('user')
        amount = obj.get('amount')
        tag = obj.get('tag', '')
        if not isinstance(user, str) or isinstance(amount, bool) or not isinstance(amount, int) \
                or not isinstance(tag, str) or amount < MINI or amount > MAXI:
            bad += 1
            continue
        c, s = tags.get(tag, (0, 0))
        tags[tag] = (c + 1, s + amount)
        users[user] = users.get(user, 0) + 1
    out = ['bad %d tags %d users %d' % (bad, len(tags), len(users))]
    for tag in sorted(tags):
        c, s = tags[tag]
        out.append('tag %s count %d total %d' % (tag, c, s))
    order = sorted(users.items(), key=lambda kv: (-kv[1], kv[0]))
    for user, c in order[:10]:
        out.append('user %s %d' % (user, c))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
