xs: list[int] = [1, 2, 3]
print("full", xs, "len", len(xs))
print("tail", xs[1:100])
print("head", xs[-100:2])
print("none", xs[100:200])
print("step", xs[::2])
print("past start", xs[5:])
print("text", "abc"[2:50])
print("done")
