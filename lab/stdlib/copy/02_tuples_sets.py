import copy

plain_tuple = (1, "two", (3, 4))
nested_tuple = ([10, 20], (30, 40))
num_set = {3, 1, 2}
frozen = frozenset([4, 5, 6])

t_shallow = copy.copy(plain_tuple)
t_deep = copy.deepcopy(plain_tuple)
nt_deep = copy.deepcopy(nested_tuple)
nested_tuple[0].append(99)

s_shallow = copy.copy(num_set)
s_deep = copy.deepcopy(num_set)
num_set.add(10)
f_shallow = copy.copy(frozen)
f_deep = copy.deepcopy(frozen)

print("plain_tuple:", t_shallow == plain_tuple, t_deep == plain_tuple)
print("nested_tuple:", nt_deep, nt_deep is nested_tuple, nt_deep[0] is nested_tuple[0])
print("set:", sorted(list(s_shallow)), sorted(list(s_deep)), s_shallow is num_set, s_deep is num_set)
print("frozenset:", sorted(list(f_shallow)), sorted(list(f_deep)), f_shallow is frozen)
