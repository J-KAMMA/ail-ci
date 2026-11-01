import json


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, Money):
            return {"cents": obj.cents}
        return super().default(obj)


def main() -> None:
    data = {"price": Money(1250), "qty": 3}
    print(json.dumps(data, cls=MoneyEncoder, sort_keys=True))
    print(json.dumps([Money(1), Money(2)], cls=MoneyEncoder, indent=2))
    print(json.dumps({"ok": True}, cls=MoneyEncoder))


main()
