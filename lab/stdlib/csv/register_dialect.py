import csv
import io

csv.register_dialect("pipe", delimiter="|", quoting=csv.QUOTE_MINIMAL)
buffer = io.StringIO()
writer = csv.writer(buffer, dialect="pipe")
writer.writerow(["a", "b|c"])
text = buffer.getvalue()
print(repr(text))
for row in csv.reader(io.StringIO(text), dialect="pipe"):
    print(row)

dialect = csv.get_dialect("pipe")
print(dialect.delimiter, dialect.quotechar, dialect.lineterminator == "\r\n")
print(dialect in csv.list_dialects(), "pipe" in csv.list_dialects())
