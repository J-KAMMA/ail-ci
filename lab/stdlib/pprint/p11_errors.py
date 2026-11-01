import pprint

cases = [("indent", -1), ("depth", 0), ("depth", -2), ("width", 0)]

for name, value in cases:
    try:
        if name == "indent":
            pprint.PrettyPrinter(indent=value)
        elif name == "depth":
            pprint.PrettyPrinter(depth=value)
        else:
            pprint.PrettyPrinter(width=value)
    except ValueError as error:
        print(name, type(error).__name__, str(error))

print(pprint.pformat({"a": 1}))
pprint.pp({"b": 2}, width=10)
print(pprint.pformat({"c": 3}, width=10))
