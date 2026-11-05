import netrc

text = """machine alpha.example.com login a password pa
machine beta.example.com login b password pb
machine gamma.example.com login c password pc
default login fallback password pf
"""
with open("multi.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("multi.netrc")
print(sorted(n.hosts.keys()))
print(len(n.hosts))
print(n.authenticators("alpha.example.com"))
print(n.authenticators("beta.example.com"))
print(n.authenticators("gamma.example.com"))
print(n.authenticators("delta.example.com"))
print(n.authenticators("delta.example.com") is n.hosts["default"])
print(n.authenticators("alpha.example.com") is n.hosts["alpha.example.com"])
