import pprint

data = {
    "name": "Ada",
    "langs": ["Python", "C", "Rust"],
    "meta": {"year": 1843, "notes": ["first", "programmer"]},
}

printer = pprint.PrettyPrinter(indent=2, width=30)
print(printer.pformat(data))
printer.pprint(data)
print(printer.isrecursive(data))
print(printer.isreadable(data))

compact = pprint.PrettyPrinter(width=25, compact=True)
print(compact.pformat([["a", "b"], ["c", "d"], ["e", "f"]]))
print(compact.isreadable([1, 2, 3]))
