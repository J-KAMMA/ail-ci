import pprint

data = {
    "zebra": 1,
    "apple": 2,
    "mango": {"pear": 4, "banana": 3},
}

print("sorted")
print(pprint.pformat(data))
print("insertion")
print(pprint.pformat(data, sort_dicts=False))
print("sorted again")
pprint.pprint(data, sort_dicts=False, width=25)

printer = pprint.PrettyPrinter(sort_dicts=False, width=20)
print(printer.pformat(data))
