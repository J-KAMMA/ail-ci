import sys


class InsufficientFunds(Exception):
    def __init__(self, account: str, missing: float) -> None:
        super().__init__(account, missing)
        self.account = account
        self.missing = missing


def fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)


def main() -> None:
    balances: dict[str, float] = {"acc1": 0.0, "acc2": 0.0, "acc3": 0.0}

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue

        command = parts[0]
        account = parts[1]
        amount = float(parts[2])

        if command == "deposit":
            balances[account] += amount
        elif command == "withdraw":
            if balances[account] < amount:
                try:
                    raise InsufficientFunds(account, amount - balances[account])
                except InsufficientFunds as exc:
                    print(f"error: {exc.account} needs {fmt(exc.missing)} more")
            else:
                balances[account] -= amount
        elif command == "balance":
            print(f"{account}={fmt(balances[account])}")

    for account in ("acc1", "acc2", "acc3"):
        print(f"{account}={fmt(balances[account])}")


if __name__ == "__main__":
    main()
