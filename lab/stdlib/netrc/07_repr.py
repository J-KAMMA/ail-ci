import netrc

text = """machine example.com login alice password pw
machine other.example.org login bob account acct2 password pw2
"""
with open("repr.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("repr.netrc")
r = repr(n)
print(r)
print(repr(r))
print(len(r))
print(r == text)

mac = """machine example.com login alice password pw
macdef init
cd /tmp

"""
with open("reprmac.netrc", "w", encoding="utf-8") as f:
    f.write(mac)

n2 = netrc.netrc("reprmac.netrc")
print(repr(n2))
