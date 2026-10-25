def args_of(d, k):
    try:
        return d[k]
    except KeyError as e:
        return e.args

def via_list(d, xs):
    try:
        return d[xs[0]]
    except KeyError as e:
        return e.args

class Box:
    def __init__(self, k: str):
        self.k: str = k

def via_attr(d, b: Box):
    try:
        return d[b.k]
    except KeyError as e:
        return e.args

def via_dict(d, meta):
    try:
        return d[meta["k"]]
    except KeyError as e:
        return e.args

GD = {"b": 1}

def via_global():
    try:
        return GD["a"]
    except KeyError as e:
        return e.args

k = "a"
alias = k
print(args_of({"b": 1}, alias))
print(args_of({1: 1}, 2))
print(args_of({-1: 1}, -2))
print(args_of({b"a": 1}, b"b"))
print(args_of({1.5: 1}, 2.5))
print(args_of({}, "missing"))
print(args_of({(1, 2): 1}, (3, 4)))
print(via_list({"b": 1}, ["a"]))
print(via_attr({"b": 1}, Box("a")))
print(via_dict({"b": 1}, {"k": "a"}))
print(via_global())

def pop_of(d, k):
    try:
        return d.pop(k)
    except KeyError as e:
        return e.args

def del_of(d, k):
    try:
        del d[k]
        return 0
    except KeyError as e:
        return e.args

def set_remove(s, x):
    try:
        s.remove(x)
        return 0
    except KeyError as e:
        return e.args

def empty_popitem():
    try:
        return {}.popitem()
    except KeyError as e:
        return (str(e), e.args)

def empty_setpop():
    try:
        return set().pop()
    except KeyError as e:
        return (str(e), e.args)

print(pop_of({"b": 1}, "a"), pop_of({"b": 1}, "b"))
print(del_of({"b": 1}, "a"), del_of({"b": 1}, "b"))
print(set_remove({1, 2}, 9), set_remove({"a"}, "b"))
print(empty_popitem(), empty_setpop())
