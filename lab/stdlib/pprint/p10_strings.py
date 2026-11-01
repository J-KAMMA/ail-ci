import pprint

texts = [
    "short",
    "a long sentence that will need to wrap across several lines when width is small",
    "line1\nline2\nline3",
    "",
]

for text in texts:
    print(pprint.pformat(text, width=25))
    print("--")

print(pprint.pformat(["alpha beta gamma delta epsilon zeta eta theta"], width=30))
print(pprint.pformat(("one two three four five six seven",), width=20))
print(pprint.pformat(b"abcdefghijklmnopqrstuvwxyz0123456789", width=20))
print(pprint.pformat(bytearray(b"abcdefghijklmnopqrstuvwxyz0123456789"), width=20))
print(pprint.pformat({"payload": b"0123456789abcdef"}, width=25))
print(pprint.pformat([b"0123456789abcdef"], width=20))
