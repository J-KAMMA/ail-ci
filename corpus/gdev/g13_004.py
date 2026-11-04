# task: Write a BankAccount base class and a SavingsAccount subclass that adds interest, then print balances after applying interest for three years.
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


class BankAccount:
    """A basic bank account that tracks an owner and a balance."""

    def __init__(self, owner: str, balance: Decimal = Decimal("0.00")) -> None:
        self.owner: str = owner
        self._balance: Decimal = balance

    @property
    def balance(self) -> Decimal:
        return self._balance

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self._balance += amount

    def withdraw(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient funds.")
        self._balance -= amount

    def __str__(self) -> str:
        return f"{self.owner}: {self._balance:.2f}"


class SavingsAccount(BankAccount):
    """A bank account that earns compound interest at an annual rate."""

    def __init__(
        self,
        owner: str,
        balance: Decimal = Decimal("0.00"),
        annual_rate: Decimal = Decimal("0.00"),
    ) -> None:
        super().__init__(owner, balance)
        self.annual_rate: Decimal = annual_rate

    def apply_interest(self) -> Decimal:
        """Apply one year of interest and return the interest earned."""
        interest = (self._balance * self.annual_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self._balance += interest
        return interest


def main() -> None:
    account = SavingsAccount(
        "Alice",
        balance=Decimal("1000.00"),
        annual_rate=Decimal("0.05"),
    )
    print(f"Starting balance: {account.balance:.2f}")
    for year in range(1, 4):
        interest = account.apply_interest()
        print(
            f"Year {year}: interest {interest:.2f}, "
            f"balance {account.balance:.2f}"
        )


if __name__ == "__main__":
    main()
