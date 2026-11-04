# C?-job-pre112-10242224-1: dict keyed by a multi-element frozenset of tuples
key = frozenset({(1, "a"), (2, "b")})
D = {key: "v"}
print(D[key])
print(frozenset({(1, "a"), (2, "b")}) in D)
print(D.get(frozenset({(1, "a"), (2, "b")})))
print(D.get(frozenset({(1, "a")})))
print(len(D))
