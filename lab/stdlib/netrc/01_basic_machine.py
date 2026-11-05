import netrc

text = """machine example.com login alice password secret123
"""
with open("basic.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("basic.netrc")
print(n.authenticators("example.com"))
print(n.authenticators("example.com")[0])
print(n.authenticators("example.com")[1])
print(n.authenticators("example.com")[2])
print(len(n.hosts))
print(sorted(n.hosts.keys()))
print(n.hosts["example.com"])
print(n.authenticators("other.org"))
print(n.authenticators("other.org") is None)
