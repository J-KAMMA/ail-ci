import netrc

text = """# a leading comment line
machine example.com login alice password pw # trailing comment
# between entries
machine other.example.org login bob password pw2
"""
with open("comments.netrc", "w", encoding="utf-8") as f:
    f.write(text)

n = netrc.netrc("comments.netrc")
print(sorted(n.hosts.keys()))
print(n.authenticators("example.com"))
print(n.authenticators("other.example.org"))
print(len(n.macros))

single = """#comment
machine solo.example.com login carol password pw3
#another
"""
with open("single.netrc", "w", encoding="utf-8") as f:
    f.write(single)

n2 = netrc.netrc("single.netrc")
print(sorted(n2.hosts.keys()))
print(n2.authenticators("solo.example.com"))
