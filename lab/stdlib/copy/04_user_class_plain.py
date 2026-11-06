import copy


class Point:
    def __init__(self, x, y, tags):
        self.x = x
        self.y = y
        self.tags = tags


p = Point(3, 4, ["a", "b"])
p_shallow = copy.copy(p)
p_deep = copy.deepcopy(p)
p.tags.append("c")

print("shallow:", p_shallow.x, p_shallow.y, p_shallow.tags, p_shallow is p)
print("deep:", p_deep.x, p_deep.y, p_deep.tags, p_deep is p)
