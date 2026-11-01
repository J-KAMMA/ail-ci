class Transaction:
    def __init__(self, name):
        self.name = name
        self.state = "new"

    def __enter__(self):
        self.state = "open"
        print("begin", self.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.state = "committed"
            print("commit", self.name, tb is None)
            return False
        print("rollback", self.name, exc_type.__name__, str(exc), tb is not None)
        if exc_type is LookupError:
            print("lookup swallowed")
            return True
        if issubclass(exc_type, ArithmeticError):
            print("arithmetic swallowed")
            return True
        if exc_type in (TypeError, AssertionError):
            print("type/assert swallowed")
            return True
        return False


def run(cm, label, mode):
    try:
        with cm as active:
            print("body", label, active.name)
            if mode == "value":
                raise ValueError(label)
            if mode == "key":
                raise KeyError(label)
            if mode == "zero":
                raise ZeroDivisionError(label)
            if mode == "type":
                raise TypeError(label)
            if mode == "assert":
                raise AssertionError(label)
            if mode == "index":
                raise IndexError(label)
        print("after", label)
    except Exception as e:
        print("caught", label, type(e).__name__, e)


run(Transaction("clean"), "clean", "none")
run(Transaction("value"), "value", "value")
run(Transaction("key"), "key", "key")
run(Transaction("zero"), "zero", "zero")
run(Transaction("type"), "type", "type")

holder = {"cm": Transaction("dict")}
run(holder["cm"], "dict", "assert")

items = [Transaction("list")]
run(items[0], "list", "index")

for i in range(3):
    with Transaction("loop%d" % i) as tx:
        if i == 1:
            continue
        if i == 2:
            break
        print("loop", tx.name, tx.state)
