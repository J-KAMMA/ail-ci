# task: Simulate a two-step bank transfer where a failure in the second step triggers a rollback of the first, then print the final balances.
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class TransferError(Exception):
    """Raised when a transfer step fails."""


@dataclass
class Bank:
    balances: Dict[str, int] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)

    def deposit(self, account: str, amount: int) -> None:
        self.balances[account] = self.balances.get(account, 0) + amount
        self.log.append(f"deposit {amount} -> {account}")

    def withdraw(self, account: str, amount: int) -> None:
        current = self.balances.get(account, 0)
        if current < amount:
            raise TransferError(
                f"insufficient funds in {account}: have {current}, need {amount}"
            )
        self.balances[account] = current - amount
        self.log.append(f"withdraw {amount} <- {account}")

    def credit(self, account: str, amount: int) -> None:
        if account not in self.balances:
            raise TransferError(f"unknown account: {account}")
        self.balances[account] += amount
        self.log.append(f"credit {amount} -> {account}")


@dataclass
class TransferStep:
    description: str
    action: "callable"  # type: ignore[valid-type]
    compensate: "callable"  # type: ignore[valid-type]


def run_transfer(bank: Bank, source: str, target: str, amount: int,
                 fail_at_step: Optional[int] = None) -> bool:
    """Run a two-step transfer with rollback on failure.

    Step 1: withdraw from source.
    Step 2: credit to target (may fail; if so, step 1 is compensated).
    Returns True on success, False if rolled back.
    """
    completed: List[TransferStep] = []

    steps: List[TransferStep] = [
        TransferStep(
            description=f"withdraw {amount} from {source}",
            action=lambda: bank.withdraw(source, amount),
            compensate=lambda: bank.deposit(source, amount),
        ),
        TransferStep(
            description=f"credit {amount} to {target}",
            action=lambda: _credit_with_fault(bank, target, amount, fail_at_step),
            compensate=lambda: bank.withdraw(target, amount),
        ),
    ]

    try:
        for index, step in enumerate(steps, start=1):
            print(f"step {index}: {step.description}")
            step.action()
            completed.append(step)
    except TransferError as exc:
        print(f"error: {exc}")
        print("rolling back...")
        for step in reversed(completed):
            print(f"  compensating: {step.description}")
            step.compensate()
        return False
    return True


def _credit_with_fault(bank: Bank, target: str, amount: int,
                       fail_at_step: Optional[int]) -> None:
    if fail_at_step == 2:
        raise TransferError("simulated failure in step 2")
    bank.credit(target, amount)


def print_balances(bank: Bank) -> None:
    print("final balances:")
    for account in sorted(bank.balances):
        print(f"  {account}: {bank.balances[account]}")


def main() -> None:
    bank = Bank(balances={"alice": 500, "bob": 200})

    print("transfer 1 (succeeds):")
    ok = run_transfer(bank, "alice", "bob", 150)
    print(f"result: {'committed' if ok else 'rolled back'}")
    print()

    print("transfer 2 (step 2 fails):")
    ok = run_transfer(bank, "alice", "bob", 100, fail_at_step=2)
    print(f"result: {'committed' if ok else 'rolled back'}")
    print()

    print_balances(bank)


if __name__ == "__main__":
    main()
