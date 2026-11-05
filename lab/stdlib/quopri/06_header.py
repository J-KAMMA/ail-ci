import quopri

header_cases = [
    b"a b",
    b"a_b",
    b"a _ b",
    b"under_score and spaces",
    b"= equals",
    b"trailing space ",
    b"tab\there",
]

for s in header_cases:
    enc = quopri.encodestring(s, header=True)
    print(repr(s), repr(enc))
    print(repr(quopri.decodestring(enc, header=True)))
    print(repr(quopri.encodestring(s, header=False)))

print(repr(quopri.decodestring(b"a_b", header=True)))
print(repr(quopri.decodestring(b"a=5Fb", header=True)))
