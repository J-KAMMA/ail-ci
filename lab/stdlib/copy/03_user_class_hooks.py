import copy


class Bag:
    def __init__(self, label, items):
        self.label = label
        self.items = items

    def __copy__(self):
        return Bag(self.label + "_shallow", self.items)

    def __deepcopy__(self, memo):
        return Bag(self.label + "_deep", copy.deepcopy(self.items, memo))


b = Bag("box", [1, 2, [3, 4]])
b_shallow = copy.copy(b)
b_deep = copy.deepcopy(b)
b.items[2].append(5)

print("shallow:", b_shallow.label, b_shallow.items)
print("deep:", b_deep.label, b_deep.items)
