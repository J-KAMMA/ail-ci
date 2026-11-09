import sys


def main():
    balances = {}
    bad = 0

    for line in sys.stdin:
        tokens = line.split()
        if not tokens:
            continue

        if len(tokens) < 3:
            bad += 1
            continue

        payer = tokens[0]
        amount_token = tokens[1]
        participants = tokens[2:]

        if not amount_token or any(c < "0" or c > "9" for c in amount_token):
            bad += 1
            continue

        significant = amount_token.lstrip("0")
        if significant == "":
            amount = 0
        else:
            if len(significant) > 13 or (
                len(significant) == 13 and significant > "1000000000000"
            ):
                bad += 1
                continue
            amount = int(significant)

        if len(set(participants)) != len(participants):
            bad += 1
            continue

        q, r = divmod(amount, len(participants))

        balances[payer] = balances.get(payer, 0) + amount
        for i, name in enumerate(participants):
            owed = q + (1 if i < r else 0)
            balances[name] = balances.get(name, 0) - owed

    output = [f"bad {bad}"]
    for name in sorted(balances):
        output.append(f"balance {name} {balances[name]}")
    output.append(f"total {sum(balances.values())}")

    sys.stdout.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
