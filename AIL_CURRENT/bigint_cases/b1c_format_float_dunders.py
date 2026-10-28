class FloatGood:
    def __float__(self): return 2.5
class FloatInt:
    def __float__(self): return 2
class FloatStr:
    def __float__(self): return "x"
class FloatNone:
    def __float__(self): return None
class FloatList:
    def __float__(self): return [1]
class FloatDict:
    def __float__(self): return {"a": 1}
class FloatTuple:
    def __float__(self): return (1,)
class FloatBig:
    def __float__(self): return 10**400
class IndexGood:
    def __index__(self): return 7
class IndexNeg:
    def __index__(self): return -3
class IndexFloat:
    def __index__(self): return 1.5
class IndexStr:
    def __index__(self): return "x"
class IndexNone:
    def __index__(self): return None
class IndexList:
    def __index__(self): return [1]
class IndexDict:
    def __index__(self): return {"a": 1}
class IndexTuple:
    def __index__(self): return (1,)
class IndexBig:
    def __index__(self): return 10**30
class IndexBigNeg:
    def __index__(self): return -(10**30)
class IndexHuge:
    def __index__(self): return 10**400
class BothGood:
    def __float__(self): return 1.5
    def __index__(self): return 7
class BothBad:
    def __float__(self): return "x"
    def __index__(self): return 7
class Empty:
    pass


def show(label, v):
    for f in ("%f", "%e", "%g"):
        try:
            print(label, f, f % v)
        except Exception as e:
            print(label, f, type(e).__name__ + ": " + str(e))


def through_argument(v):
    show("arg", v)


class Holder:
    pass


h = Holder()
h.v = IndexFloat()
h.g = IndexGood()
items = [FloatStr(), FloatGood()]
table = {"v": IndexFloat(), "g": IndexGood()}
through_argument(IndexFloat())
through_argument(IndexGood())
show("list", items[0])
show("goodlist", items[1])
show("attr", h.v)
show("goodattr", h.g)
show("dict", table["v"])
show("gooddict", table["g"])

for o in (FloatGood(), FloatInt(), FloatStr(), FloatNone(), FloatList(), FloatDict(), FloatTuple(),
          FloatBig(), IndexGood(), IndexNeg(), IndexFloat(), IndexStr(), IndexNone(), IndexList(),
          IndexDict(), IndexTuple(), IndexBig(), IndexBigNeg(), IndexHuge(), BothGood(), BothBad(),
          Empty()):
    for f in ("%f", "%e", "%g"):
        try:
            print(type(o).__name__, f, f % o)
        except Exception as e:
            print(type(o).__name__, f, type(e).__name__ + ": " + str(e))
