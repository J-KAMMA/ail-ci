import json
import sys


def _reject_constant(name):
    raise ValueError("invalid constant: " + name)


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")

    bad = 0
    tag_count = {}
    tag_sum = {}
    user_count = {}

    lo = -9223372036854775808
    hi = 9223372036854775807

    for raw in lines:
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

        if "user" not in obj or type(obj["user"]) is not str:
            bad += 1
            continue
        user = obj["user"]

        if "amount" not in obj:
            bad += 1
            continue
        amount = obj["amount"]
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
        tag_sum[tag] = tag_sum.get(tag, 0) + amount
        user_count[user] = user_count.get(user, 0) + 1

    out = []
    out.append(
        "bad %d tags %d users %d" % (bad, len(tag_count), len(user_count))
    )
    for tag in sorted(tag_count):
        out.append(
            "tag %s count %d total %d" % (tag, tag_count[tag], tag_sum[tag])
        )
    ranked = sorted(user_count.items(), key=lambda kv: (-kv[1], kv[0]))
    for user, c in ranked[:10]:
        out.append("user %s %d" % (user, c))

    text_out = "\n".join(out) + "\n"
    sys.stdout.buffer.write(text_out.encode("utf-8", "surrogatepass"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
