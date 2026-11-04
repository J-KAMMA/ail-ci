import html.entities as E

keys = [
    "amp;", "amp", "lt;", "lt", "gt;", "quot;", "apos;",
    "notin;", "not", "copy;", "AElig;", "fjlig;", "nbsp;",
]

for key in keys:
    print(key, repr(E.html5[key]))

print(len(E.html5))
print(repr(E.html5.get("bogus;", "missing")))
print(repr(E.html5["amp;"] + E.html5["lt;"] + E.html5["gt;"]))
print(repr(E.html5["lt;"] + E.html5["gt;"]))
print(repr(E.html5["copy;"]), len(E.html5["copy;"]))
