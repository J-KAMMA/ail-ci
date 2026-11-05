# C?-job-pre175-10250446-1: dict keyed by a one-element frozenset of tuples
key = frozenset({(1, "a")})
D = {key: "v"}
print(D[key])
print(frozenset({(1, "a")}) in D)
print(D.get(frozenset({(1, "a")})))
print(D.get(frozenset({(2, "b")})))
print(len(D))
