import csv
import io

buffer = io.StringIO()
writer = csv.writer(buffer, quoting=csv.QUOTE_NONNUMERIC)
writer.writerow(["text", 42, 3.5, ""])
text = buffer.getvalue()
print(repr(text))

reader = csv.reader(io.StringIO(text), quoting=csv.QUOTE_NONNUMERIC)
row = next(reader)
print(row)
print([type(value).__name__ for value in row])
print(list(reader))

written = io.StringIO()
csv.writer(written, quoting=csv.QUOTE_NONNUMERIC).writerow([1.5, -2, "7"])
print(repr(written.getvalue()))
parsed = list(csv.reader(io.StringIO('"x",1,2.5\n'), quoting=csv.QUOTE_NONNUMERIC))
print(parsed)
print([type(value).__name__ for value in parsed[0]])
