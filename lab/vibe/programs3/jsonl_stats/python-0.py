import sys
import json


def _reject_constant(value):
    raise ValueError("invalid JSON constant: " + value)


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")

    bad = 0
    tag_stats = {}      # tag -> [count, total]
    user_counts = {}    # user -> count

    for raw in lines:
        if raw.endswith(b"\r"):
            raw = raw[:-1]

        if raw.strip(b" \t") == b"":
            continue

        try:
            obj = json.loads(raw, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            bad += 1
            continue

        if not isinstance(obj, dict):
            bad += 1
            continue

        user = obj.get("user", None)
        if not isinstance(user, str):
            bad += 1
            continue

        if "amount" not in obj:
            bad += 1
            continue
        amount = obj["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int):
            bad += 1
            continue
        if amount < -9223372036854775808 or amount > 9223372036854775807:
            bad += 1
            continue

        if "tag" in obj:
            tag = obj["tag"]
            if not isinstance(tag, str):
                bad += 1
                continue
        else:
            tag = ""

        if tag in tag_stats:
            entry = tag_stats[tag]
            entry[0] += 1
            entry[1] += amount
        else:
            tag_stats[tag] = [1, amount]

        user_counts[user] = user_counts.get(user, 0) + 1

    out = []
    out.append(
        "bad %d tags %d users %d" % (bad, len(tag_stats), len(user_counts))
    )
    for tag in sorted(tag_stats):
        count, total = tag_stats[tag]
        out.append("tag %s count %d total %d" % (tag, count, total))

    ordered_users = sorted(user_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for user, count in ordered_users[:10]:
        out.append("user %s %d" % (user, count))

    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
