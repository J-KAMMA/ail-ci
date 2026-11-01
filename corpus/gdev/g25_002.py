# task: Write a vending machine state machine with states IDLE, COLLECTING, and DISPENSING, and simulate a fixed sequence of coin inserts and print each state change.
from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field


class State(Enum):
    IDLE = auto()
    COLLECTING = auto()
    DISPENSING = auto()


@dataclass
class VendingMachine:
    price_cents: int = 150
    state: State = State.IDLE
    balance_cents: int = 0
    log: list[str] = field(default_factory=list)

    def _transition(self, new_state: State, reason: str) -> None:
        old = self.state
        self.state = new_state
        line = f"[{old.name:<10}] -> [{new_state.name:<10}] ({reason})"
        self.log.append(line)
        print(line)

    def insert_coin(self, cents: int) -> None:
        if cents not in (5, 10, 25, 100):
            print(f"Rejected coin of {cents} cents (not accepted)")
            return

        if self.state is State.IDLE:
            self.balance_cents = 0
            self._transition(State.COLLECTING, f"coin {cents}c inserted")
        elif self.state is State.COLLECTING:
            pass  # stay in collecting; still accumulating
        else:
            print(f"Ignoring coin {cents}c: machine is {self.state.name}")
            return

        self.balance_cents += cents
        print(f"  balance: {self.balance_cents}c / price: {self.price_cents}c")

        if self.balance_cents >= self.price_cents:
            self._transition(State.DISPENSING, "price reached")
            self.dispense()

    def dispense(self) -> None:
        change = self.balance_cents - self.price_cents
        print(f"  dispensing item, change returned: {change}c")
        self.balance_cents = 0
        self._transition(State.IDLE, "item dispensed")


def main() -> None:
    machine = VendingMachine(price_cents=150)
    coin_sequence = [25, 100, 10, 25, 5, 100, 25, 25, 10]
    print(f"Initial state: {machine.state.name}")
    for coin in coin_sequence:
        print(f"Insert coin: {coin}c")
        machine.insert_coin(coin)
    print(f"Final state: {machine.state.name}, balance: {machine.balance_cents}c")


if __name__ == "__main__":
    main()
