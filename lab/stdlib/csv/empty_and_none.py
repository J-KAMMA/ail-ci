import csv
import io

buffer = io.StringIO()
writer = csv.writer(buffer)
writer.writerow([])
writer.writerow([""])
writer.writerow([None, "x"])
print(repr(buffer.getvalue()))

reader = csv.reader(io.StringIO(""))
print(next(reader, None))
print(list(reader))
print(list(csv.reader(io.StringIO("\n\r\n"))))

empty = io.StringIO()
print(repr(empty.getvalue()))
print(list(csv.reader(io.StringIO(empty.getvalue()))))
