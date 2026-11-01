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
