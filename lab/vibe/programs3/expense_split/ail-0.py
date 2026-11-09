import sys


def parse_amount(token):
    if not token:
        return None
    for ch in token:
        if ch < '0' or ch > '9':
            return None

    digits = token.lstrip('0')
    if not digits:
        return 0
    if len(digits) > 13:
        return None

    value = int(digits)
    if value > 1000000000000:
        return None
    return value


def main():
    data = sys.stdin.read()
    balances = {}
    bad = 0

    for line in data.split('\n'):
        parts = line.split()
        if not parts:
            continue

        if len(parts) < 3:
            bad += 1
            continue

        payer = parts[0]
        amount = parse_amount(parts[1])
        if amount is None:
            bad += 1
            continue

        participants = parts[2:]
        if len(set(participants)) != len(participants):
            bad += 1
            continue

        count = len(participants)
        q, r = divmod(amount, count)

        balances[payer] = balances.get(payer, 0) + amount

        for i, person in enumerate(participants):
            owes = q + 1 if i < r else q
            balances[person] = balances.get(person, 0) - owes

    output = ["bad " + str(bad)]

    for name in sorted(balances):
        output.append("balance " + name + " " + str(balances[name]))

    output.append("total " + str(sum(balances.values())))

    sys.stdout.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
