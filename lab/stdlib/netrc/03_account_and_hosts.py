import netrc

text = """machine a.example.com login u1 account acct1 password p1
machine b.example.com login u2 password p2
machine c.example.com login u3 account acct3 password p3
"""
with open("accounts.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("accounts.netrc")
print(sorted(n.hosts.keys()))
for host in sorted(n.hosts.keys()):
    print(host, n.hosts[host])
print(n.authenticators("a.example.com"))
print(n.authenticators("b.example.com")[1])
print(repr(n.authenticators("b.example.com")[1]))
print(n.authenticators("c.example.com")[1])
