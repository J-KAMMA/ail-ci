from typing import NewType

UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)
Email = NewType("Email", str)


def label(uid: UserId) -> str:
    return "user-" + str(uid)


def next_order(order: OrderId) -> OrderId:
    return OrderId(int(order) + 1)


def normalize(email: Email) -> Email:
    return Email(email.strip().lower())


def main() -> None:
    u = UserId(42)
    print(u)
    print(label(u))
    print(u + 1)
    o = OrderId(100)
    print(next_order(o))
    print(next_order(o) == 101)
    e = Email("  Ada@Example.COM ")
    print(normalize(e))
    print(len(normalize(e)))
    ids = [UserId(1), UserId(2), UserId(3)]
    print(ids)
    print(sum(ids))


main()
