import html.entities as E

print(E.name2codepoint["lt"], E.name2codepoint["amp"], E.name2codepoint["AElig"])
print(E.codepoint2name[60], E.codepoint2name[38], E.codepoint2name[198])
print(repr(E.entitydefs["lt"]), repr(E.entitydefs["quot"]))
print(len(E.name2codepoint), len(E.codepoint2name), len(E.entitydefs))

for name in ["lt", "gt", "amp", "quot", "copy", "nbsp"]:
    print(name, E.name2codepoint[name], repr(E.entitydefs[name]))

print(E.name2codepoint.get("lt"), E.name2codepoint.get("bogus"))
print(E.codepoint2name.get(60), E.codepoint2name.get(999999))
print(E.entitydefs["amp"], E.entitydefs["gt"])
print(E.name2codepoint.get("copy"), E.entitydefs.get("copy"))
print(len(E.html5))
