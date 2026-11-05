# C?-job-pre138-10250109-1: integer modulo by zero names the operation
try:
    print(1 % 0)
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    print(1 // 0)
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    print(divmod(1, 0))
except Exception as exc:
    print(type(exc).__name__, str(exc))
x = 0
try:
    print(1 % x)
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    print(1 % 0.0)
except Exception as exc:
    print(type(exc).__name__, str(exc))
