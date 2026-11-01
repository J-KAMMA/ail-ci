import pprint

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
mapping = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
pairs = [["alpha", 1], ["beta", 2], ["gamma", 3], ["delta", 4]]

print("compact")
print(pprint.pformat(numbers, width=40, compact=True))
print(pprint.pformat(mapping, width=30, compact=True))
print(pprint.pformat(pairs, width=32, compact=True))
print("wide")
print(pprint.pformat(numbers, width=40, compact=False))
print(pprint.pformat(mapping, width=30, compact=False))
print(pprint.pformat(pairs, width=32, compact=False))
pprint.pprint([numbers, mapping], width=35, compact=True)
