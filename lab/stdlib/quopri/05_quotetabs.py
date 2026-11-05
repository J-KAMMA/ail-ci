import quopri

cases = [
    b"a\tb",
    b"a b",
    b"trailing tab\t",
    b"trailing space ",
    b"a\tb c",
    b"\tleading",
    b" middle \t end ",
]

for s in cases:
    print(repr(s))
    print("false", repr(quopri.encodestring(s)))
    print("true ", repr(quopri.encodestring(s, quotetabs=True)))

print(repr(quopri.decodestring(quopri.encodestring(b"a\tb", quotetabs=True))))
print(repr(quopri.decodestring(quopri.encodestring(b"a b", quotetabs=False))))
