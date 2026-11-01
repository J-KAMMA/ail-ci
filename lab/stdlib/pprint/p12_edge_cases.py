import pprint

print(pprint.pformat({}))
print(pprint.pformat([]))
print(pprint.pformat(()))
print(pprint.pformat((1,)))
print(pprint.pformat(set()))
print(pprint.pformat(frozenset()))

data = {"empty": {}, "list": [], "tuple": (), "nested": [[], {}, [1, 2]]}
print(pprint.pformat(data, width=20))

printer = pprint.PrettyPrinter(depth=1)
print(printer.pformat([[], {}, [1, 2], {"a": 1}]))
print(pprint.saferepr((1,)))
print(pprint.saferepr({}))
