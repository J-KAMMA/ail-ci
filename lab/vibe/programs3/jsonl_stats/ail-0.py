import sys
import json

MIN_AMOUNT = -9223372036854775807 - 1
MAX_AMOUNT = 9223372036854775807


def _parse_int(text):
    if text == "":
        return None
    if text == "-9223372036854775808":
        return MIN_AMOUNT

    index = 0
    negative = False
    if text[0] == "-":
        negative = True
        index = 1

    value = 0
    length = len(text)
    while index < length:
        digit = ord(text[index]) - 48
        if value > (MAX_AMOUNT - digit) // 10:
            return None
        value = value * 10 + digit
        index += 1

    if negative:
        return -value
    return value


def _reject_constant(text):
    raise ValueError("invalid JSON constant")


def _safe_sum(values):
    positives = []
    negatives = []
    for value in values:
        if value > 0:
            positives.append(value)
        else:
            negatives.append(value)

    total = 0
    while positives and negatives:
        if total > 0:
            total += negatives.pop()
        else:
            total += positives.pop()

    while positives:
        total += positives.pop()
    while negatives:
        total += negatives.pop()

    return total


def _encode_utf8(text):
    out = []
    for ch in text:
        cp = ord(ch)
        if cp < 0x80:
            out.append(cp)
        elif cp < 0x800:
            out.append(0xC0 | (cp >> 6))
            out.append(0x80 | (cp & 0x3F))
        elif cp < 0x10000:
            out.append(0xE0 | (cp >> 12))
            out.append(0x80 | ((cp >> 6) & 0x3F))
            out.append(0x80 | (cp & 0x3F))
        else:
            out.append(0xF0 | (cp >> 18))
            out.append(0x80 | ((cp >> 12) & 0x3F))
            out.append(0x80 | ((cp >> 6) & 0x3F))
            out.append(0x80 | (cp & 0x3F))
    return bytes(out)


def _emit(text):
    sys.stdout.buffer.write(_encode_utf8(text))


def main():
    data = sys.stdin.buffer.read()
    bad = 0

    tag_index = {}
    tag_names = []
    tag_counts = []
    tag_amounts = []

    user_index = {}
    user_names = []
    user_counts = []

    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]

        if raw == b"" or raw.strip(b" \t") == b"":
            continue

        try:
            line = raw.decode("utf-8")
            obj = json.loads(
                line,
                parse_int=_parse_int,
                parse_constant=_reject_constant,
            )
        except Exception:
            bad += 1
            continue

        if not isinstance(obj, dict):
            bad += 1
            continue

        if "user" not in obj or not isinstance(obj["user"], str):
            bad += 1
            continue

        if "amount" not in obj:
            bad += 1
            continue

        amount = obj["amount"]
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < MIN_AMOUNT
            or amount > MAX_AMOUNT
        ):
            bad += 1
            continue

        if "tag" in obj:
            tag = obj["tag"]
            if not isinstance(tag, str):
                bad += 1
                continue
        else:
            tag = ""

        user = obj["user"]

        if user in user_index:
            ui = user_index[user]
            user_counts[ui] += 1
        else:
            ui = len(user_names)
            user_index[user] = ui
            user_names.append(user)
            user_counts.append(1)

        if tag in tag_index:
            ti = tag_index[tag]
            tag_counts[ti] += 1
            tag_amounts[ti].append(amount)
        else:
            ti = len(tag_names)
            tag_index[tag] = ti
            tag_names.append(tag)
            tag_counts.append(1)
            tag_amounts.append([amount])

    _emit(
        "bad "
        + str(bad)
        + " tags "
        + str(len(tag_names))
        + " users "
        + str(len(user_names))
        + "\n"
    )

    tag_order = list(range(len(tag_names)))
    tag_order.sort(key=lambda i: tag_names[i])

    for ti in tag_order:
        _emit(
            "tag "
            + tag_names[ti]
            + " count "
            + str(tag_counts[ti])
            + " total "
            + str(_safe_sum(tag_amounts[ti]))
            + "\n"
        )

    n_users = len(user_names)
    used = []
    for _ in range(n_users):
        used.append(False)

    limit = n_users
    if limit > 10:
        limit = 10

    for _ in range(limit):
        best = -1
        for i in range(n_users):
            if used[i]:
                continue
            if best == -1:
                best = i
            elif user_counts[i] > user_counts[best]:
                best = i
            elif (
                user_counts[i] == user_counts[best]
                and user_names[i] < user_names[best]
            ):
                best = i

        used[best] = True
        _emit("user " + user_names[best] + " " + str(user_counts[best]) + "\n")


if __name__ == "__main__":
    main()
