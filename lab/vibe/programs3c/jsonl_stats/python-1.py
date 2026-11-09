import sys
import json


def _reject_constant(name):
    raise ValueError("invalid constant: " + name)


def main():
    data = sys.stdin.buffer.read()
    bad = 0
    tag_count = {}
    tag_total = {}
    user_count = {}
    lo, hi = -9223372036854775808, 9223372036854775807

    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if raw.strip(b" \t") == b"":
            continue
        try:
            text = raw.decode("utf-8")
            obj = json.loads(text, parse_constant=_reject_constant)
        except Exception:
            bad += 1
            continue

        if not isinstance(obj, dict):
            bad += 1
            continue

        user = obj.get("user")
        if type(user) is not str:
            bad += 1
            continue

        amount = obj.get("amount")
        if type(amount) is not int or not (lo <= amount <= hi):
            bad += 1
            continue

        if "tag" in obj:
            tag = obj["tag"]
            if type(tag) is not str:
                bad += 1
                continue
        else:
            tag = ""

        tag_count[tag] = tag_count.get(tag, 0) + 1
        tag_total[tag] = tag_total.get(tag, 0) + amount
        user_count[user] = user_count.get(user, 0) + 1

    out = []
    out.append("bad %d tags %d users %d" % (bad, len(tag_count), len(user_count)))
    for tag in sorted(tag_count):
        out.append("tag %s count %d total %d" % (tag, tag_count[tag], tag_total[tag]))
    top = sorted(user_count.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    for user, c in top:
        out.append("user %s %d" % (user, c))

    text = "".join(line + "\n" for line in out)
    sys.stdout.buffer.write(text.encode("utf-8", errors="surrogatepass"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
