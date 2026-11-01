import csv
import io

for text in ['a,"unterminated\n', '"a"b,c\n', 'ok,1\n']:
    try:
        rows = []
        for row in csv.reader(io.StringIO(text), strict=True):
            rows.append(row)
        print("ok", rows)
    except csv.Error as exc:
        print("csv error:", exc)
print("done")

try:
    list(csv.reader(io.StringIO('x\ry\n')))
except csv.Error as exc:
    print("newline error:", exc)
