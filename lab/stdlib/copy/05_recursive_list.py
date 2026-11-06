import copy

cyc = [10, 20]
cyc.append(cyc)

memo = {}
dup = copy.deepcopy(cyc, memo)

print("len:", len(dup))
print("heads:", dup[0], dup[1])
print("self_cycle:", dup[2] is dup, dup is cyc)

d = {"name": "root"}
d["self"] = d
d_dup = copy.deepcopy(d)
print("dict_cycle:", d_dup["name"], d_dup["self"] is d_dup, d_dup is d)
