# task: Build a dataclass with InitVar parameter that is used only during initialization to compute a derived field.
from dataclasses import dataclass, field, InitVar


@dataclass
class Rectangle:
    width: float
    height: float
    scale: InitVar[float] = 1.0
    area: float = field(init=False)
    perimeter: float = field(init=False)

    def __post_init__(self, scale: float) -> None:
        # The InitVar 'scale' is only available here, during initialization.
        self.width = self.width * scale
        self.height = self.height * scale
        self.area = self.width * self.height
        self.perimeter = 2 * (self.width + self.height)


@dataclass
class Account:
    owner: str
    balance: float = field(init=False)
    initial_deposit: InitVar[float] = 0.0
    fee_rate: InitVar[float] = 0.01

    def __post_init__(self, initial_deposit: float, fee_rate: float) -> None:
        fee = initial_deposit * fee_rate
        self.balance = initial_deposit - fee


def main() -> None:
    r1 = Rectangle(3.0, 4.0)
    r2 = Rectangle(3.0, 4.0, scale=2.0)
    print(f"r1: width={r1.width}, height={r1.height}, "
          f"area={r1.area}, perimeter={r1.perimeter}")
    print(f"r2: width={r2.width}, height={r2.height}, "
          f"area={r2.area}, perimeter={r2.perimeter}")

    acct = Account("alice", initial_deposit=200.0)
    print(f"owner={acct.owner}, balance={acct.balance:.2f}")
    print("InitVar fields are not stored as attributes:",
          not hasattr(acct, "initial_deposit") and not hasattr(acct, "fee_rate"))


if __name__ == "__main__":
    main()
