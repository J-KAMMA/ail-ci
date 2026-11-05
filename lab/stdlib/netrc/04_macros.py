import netrc

text = """machine example.com login alice password pw
macdef init
cd /tmp
ls -l

macdef upload
put file
mput *.txt

"""
with open("macros.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("macros.netrc")
print(sorted(n.macros.keys()))
for name in sorted(n.macros.keys()):
    print(name, len(n.macros[name]))
    print(n.macros[name])
print(n.authenticators("example.com"))
print(repr(n.macros["init"]))
print(repr(n.macros["upload"]))
