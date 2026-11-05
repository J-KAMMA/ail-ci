import netrc

text = 'machine example.com login "john doe" password "pa ss\\\\word"\n'
with open("quoted.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("quoted.netrc")
print(n.authenticators("example.com"))
print(repr(n.authenticators("example.com")[0]))
print(repr(n.authenticators("example.com")[2]))
print(len(n.authenticators("example.com")[2]))

plain = 'machine "host with space" login "a b" password "c d"\n'
with open("spaces.netrc", "w", encoding="utf-8") as f:
    f.write(plain)

n2 = netrc.netrc("spaces.netrc")
print(sorted(n2.hosts.keys()))
print(n2.authenticators("host with space"))
print(repr(n2.authenticators("host with space")[0]))
