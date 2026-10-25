d = {}
a = 2**63-1
d["k"] = a+1
l = [a, a]
print(d["k"], l[0]*l[1], -(a+1), abs(-a-1))
