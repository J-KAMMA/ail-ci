# C?-job-rbfuzz4-10240913-3: same-size delete+reinsert during live dict iteration.
d = {1: "a", 2: "b", 3: "c"}
try:
    for k in d:
        print(k)
        if k == 1:
            del d[1]
            d[1] = "a"
    print("done")
except RuntimeError as e:
    print("runtime", e)
