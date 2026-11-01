from abc import ABC, abstractmethod


class Payment(ABC):
    def __init__(self, amount: int) -> None:
        self.amount = amount

    @abstractmethod
    def fee(self) -> int:
        ...

    def total(self) -> int:
        return self.amount + self.fee()

    def receipt(self) -> str:
        return "%s total=%d fee=%d" % (type(self).__name__, self.total(), self.fee())


class Card(Payment):
    def fee(self) -> int:
        return self.amount // 20


class Cash(Payment):
    def fee(self) -> int:
        return 0


class GiftCard(Card):
    def fee(self) -> int:
        base = Card.fee(self)
        if self.amount > 500:
            return base
        return base + 1


payments = [Card(100), Cash(100), GiftCard(100), GiftCard(1000)]
for payment in payments:
    print(payment.receipt())
print("income", sum(p.total() for p in payments))
