# task: Define a custom exception hierarchy for a bank account with InsufficientFunds and AccountLocked subclasses, then raise and catch each one and print its message.
from __future__ import annotations


class BankAccountError(Exception):
    """Base exception for all bank account errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InsufficientFunds(BankAccountError):
    """Raised when a withdrawal exceeds the available balance."""

    def __init__(self, balance: float, requested: float) -> None:
        self.balance = balance
        self.requested = requested
        super().__init__(
            f"Insufficient funds: balance is {balance:.2f}, "
            f"requested {requested:.2f}"
        )


class AccountLocked(BankAccountError):
    """Raised when an operation is attempted on a locked account."""

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        super().__init__(f"Account {account_id} is locked")


class BankAccount:
    """A simple bank account that can be locked and withdrawn from."""

    def __init__(self, account_id: str, balance: float) -> None:
        self.account_id = account_id
        self.balance = balance
        self.locked = False

    def lock(self) -> None:
        self.locked = True

    def withdraw(self, amount: float) -> None:
        if self.locked:
            raise AccountLocked(self.account_id)
        if amount > self.balance:
            raise InsufficientFunds(self.balance, amount)
        self.balance -= amount


def main() -> None:
    account = BankAccount("ACC-1001", 100.0)

    # Trigger and catch InsufficientFunds
    try:
        account.withdraw(250.0)
    except InsufficientFunds as exc:
        print(f"Caught {type(exc).__name__}: {exc.message}")
        print(f"  balance={exc.balance:.2f}, requested={exc.requested:.2f}")

    # Trigger and catch AccountLocked
    account.lock()
    try:
        account.withdraw(10.0)
    except AccountLocked as exc:
        print(f"Caught {type(exc).__name__}: {exc.message}")
        print(f"  account_id={exc.account_id}")

    # Both are catchable via the common base class
    try:
        account.withdraw(1.0)
    except BankAccountError as exc:
        print(f"Base handler caught: {exc}")


if __name__ == "__main__":
    main()
