import netrc

text = """machine example.com login alice password pw1
default login guest password anon
"""
with open("withdefault.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("withdefault.netrc")
print(n.authenticators("example.com"))
print(n.authenticators("unknown.example.org"))
print(sorted(n.hosts.keys()))

plain = """machine example.com login bob password pw2
"""
with open("nodefault.netrc", "w", encoding="utf-8") as f:
    f.write(plain)

n2 = netrc.netrc("nodefault.netrc")
print(n2.authenticators("example.com"))
print(n2.authenticators("unknown.example.org"))
print(n2.authenticators("unknown.example.org") is None)
print(sorted(n2.hosts.keys()))
