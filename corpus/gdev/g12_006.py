# task: Simulate daily interest accrual on several bank accounts with a fixed schedule of deposits and withdrawals, then print each account's final balance.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, getcontext


getcontext().prec = 28


@dataclass
class Account:
    name: str
    balance: Decimal
    annual_rate: Decimal  # e.g. Decimal("0.025") for 2.5% APR
    transactions: dict[date, list[Decimal]] = field(default_factory=dict)

    def schedule(self, when: date, amount: Decimal) -> None:
        """Record a deposit (positive) or withdrawal (negative) on a date."""
        self.transactions.setdefault(when, []).append(amount)

    def apply_day(self, day: date) -> None:
        """Apply the day's transactions, then accrue one day of interest."""
        for amount in self.transactions.get(day, []):
            self.balance += amount
        # Simple daily interest on a 365-day year, rounded to cents each day.
        daily_interest = (self.balance * self.annual_rate / Decimal(365)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        self.balance += daily_interest


def build_accounts() -> list[Account]:
    start = date(2024, 1, 1)
    accounts = [
        Account("Checking", Decimal("1000.00"), Decimal("0.0100")),
        Account("Savings", Decimal("5000.00"), Decimal("0.0425")),
        Account("Money Market", Decimal("2500.00"), Decimal("0.0350")),
        Account("Retirement", Decimal("12000.00"), Decimal("0.0500")),
    ]

    checking, savings, money_market, retirement = accounts

    # Checking: regular paycheck deposits and bill payments.
    for day_offset in range(0, 366, 14):
        checking.schedule(start + timedelta(days=day_offset), Decimal("850.00"))
    for day_offset in range(5, 366, 30):
        checking.schedule(start + timedelta(days=day_offset), Decimal("-420.50"))
    for day_offset in range(20, 366, 30):
        checking.schedule(start + timedelta(days=day_offset), Decimal("-199.99"))

    # Savings: monthly transfers in, one large withdrawal.
    for month in range(1, 13):
        savings.schedule(date(2024, month, 1), Decimal("300.00"))
    savings.schedule(date(2024, 6, 15), Decimal("-2000.00"))

    # Money market: quarterly deposits.
    for month in (1, 4, 7, 10):
        money_market.schedule(date(2024, month, 10), Decimal("1500.00"))
    money_market.schedule(date(2024, 9, 1), Decimal("-500.00"))

    # Retirement: annual contribution and one early withdrawal.
    retirement.schedule(date(2024, 3, 31), Decimal("6000.00"))
    retirement.schedule(date(2024, 11, 5), Decimal("-1500.00"))

    return accounts


def main() -> None:
    accounts = build_accounts()
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)

    day = start
    while day <= end:
        for account in accounts:
            account.apply_day(day)
        day += timedelta(days=1)

    print(f"Daily interest accrual simulation: {start.isoformat()} to {end.isoformat()}")
    for account in accounts:
        print(f"{account.name:<15} final balance: {account.balance:>12.2f}")


if __name__ == "__main__":
    main()
