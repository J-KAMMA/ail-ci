# C?-job-qtest3-10241647-1: str.partition/rpartition separator type errors
s = "a=b=c"

def line(value):
    print(type(value).__name__, str(value))

try:
    line(s.partition(1))
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    line(s.rpartition(1.5))
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    line(s.partition(None))
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    line(s.rpartition(None))
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    line(s.partition(""))
except Exception as exc:
    print(type(exc).__name__, str(exc))
print(s.partition("="), s.rpartition("="))
print(b"a=b".partition(b"="))
