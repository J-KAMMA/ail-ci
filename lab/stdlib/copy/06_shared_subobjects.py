import copy

shared = [7, 8]
holder = [shared, shared, {"inner": shared}]

dup = copy.deepcopy(holder)
shared.append(9)

print("orig_shared:", shared)
print("dup_values:", dup[0], dup[1], dup[2]["inner"])
print("still_shared:", dup[0] is dup[1], dup[0] is dup[2]["inner"])
print("distinct_from_orig:", dup[0] is shared, dup is holder)
