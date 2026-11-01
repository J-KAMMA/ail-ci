import pprint

data = {
    "count": 1234567,
    "small": 42,
    "negative": -9876543,
    "nested": [1000, 2000000],
}

print(pprint.pformat(data, underscore_numbers=True))
print(pprint.pformat(data))
pprint.pprint(data, underscore_numbers=True, width=30)
print(pprint.pformat(-1234567890, underscore_numbers=True))
print(pprint.pformat([1234, 5678, 9012345], width=20, underscore_numbers=True))
printer = pprint.PrettyPrinter(width=18, underscore_numbers=True)
print(printer.pformat({"big": 9999999, "tiny": 7}))
