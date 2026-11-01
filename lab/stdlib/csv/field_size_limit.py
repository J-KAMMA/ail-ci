import csv
import io

old = csv.field_size_limit()
print("default limit positive:", old > 0)
csv.field_size_limit(10)
try:
    next(csv.reader(io.StringIO("x" * 50 + "\n")))
except csv.Error as exc:
    print("too long:", exc)
csv.field_size_limit(old)
print(next(csv.reader(io.StringIO("short\n"))))
