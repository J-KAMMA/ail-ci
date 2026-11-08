import copy

orig = {"nums": [1, 2, [3, 4]], "meta": {"tag": "v1", "count": 10}}
shallow = copy.copy(orig)
deep = copy.deepcopy(orig)

orig["nums"].append(99)
orig["nums"][2].append(5)
orig["meta"]["count"] = 20

print("orig:", orig["nums"], orig["meta"]["count"])
print("shallow:", shallow["nums"], shallow["meta"]["count"])
print("deep:", deep["nums"], deep["meta"]["count"])
print("identities:", shallow is orig, deep is orig, shallow["nums"] is orig["nums"], deep["nums"] is orig["nums"])
