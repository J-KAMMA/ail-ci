# C?-job-rbfuzz4-10240913-2: dict/set literals evaluate all entries before hashing
log = []

def val(n):
    log.append(n)
    return n

try:
    d = {[1]: val("a"), "b": val("c")}
except Exception as exc:
    print(type(exc).__name__, str(exc))
print(log)

log = []
try:
    s = {[1], val(2)}
except Exception as exc:
    print(type(exc).__name__, str(exc))
print(log)

log = []
d2 = {"x": val(1), "y": val(2)}
print(d2, log)
