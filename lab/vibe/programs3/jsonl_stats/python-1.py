import sys
import json

INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807


def reject_constant(value):
    raise ValueError("invalid JSON constant")


def main():
    data = sys.stdin.buffer.read().decode("utf-8")

    bad = 0
    tag_counts = {}
    tag_totals = {}
    user_counts = {}

    for raw in data.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw

        if line == "" or line.strip(" \t") == "":
            continue

        try:
            obj = json.loads(line, parse_constant=reject_constant)
        except Exception:
            bad += 1
            continue

        if not isinstance(obj, dict):
            bad += 1
            continue

        if "user" not in obj or "amount" not in obj:
            bad += 1
            continue

        user = obj["user"]
        amount = obj["amount"]
        tag = obj.get("tag", "")

        if not isinstance(user, str):
            bad += 1
            continue

        if not isinstance(amount, int) or isinstance(amount, bool):
            bad += 1
            continue

        if amount < INT64_MIN or amount > INT64_MAX:
            bad += 1
            continue

        if not isinstance(tag, str):
            bad += 1
            continue

        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tag_totals[tag] = tag_totals.get(tag, 0) + amount
        user_counts[user] = user_counts.get(user, 0) + 1

    out = [f"bad {bad} tags {len(tag_counts)} users {len(user_counts)}"]

    for tag in sorted(tag_counts):
        out.append(f"tag {tag} count {tag_counts[tag]} total {tag_totals[tag]}")

    top_users = sorted(user_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    for user, count in top_users:
        out.append(f"user {user} {count}")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
