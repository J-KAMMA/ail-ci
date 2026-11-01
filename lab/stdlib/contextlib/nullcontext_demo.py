from contextlib import nullcontext


def show(label, cm):
    with cm as value:
        print(label, value)


show("empty", nullcontext())
show("value", nullcontext(42))
show("keyword", nullcontext(enter_result="kw"))
show("none", nullcontext(None))
show("empty-string", nullcontext(""))

cm = nullcontext([1, 2])
with cm as xs:
    xs.append(3)
print("attribute", cm.enter_result)

with nullcontext(5) as five:
    print("five", five)
    with nullcontext("inner") as inner:
        print("inner", inner)
    print("back", five)

try:
    with nullcontext("body"):
        raise KeyError("not suppressed")
except KeyError as e:
    print("error", e)

items = [nullcontext("list"), nullcontext("other")]
with items[0] as picked:
    print("list", picked)

box = {"cm": nullcontext("dict")}
with box["cm"] as picked:
    print("dict", picked)

for i in range(3):
    with nullcontext(i) as value:
        if value == 1:
            continue
        print("loop", value)
