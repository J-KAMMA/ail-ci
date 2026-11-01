import csv
import io

buffer = io.StringIO()
writer = csv.writer(buffer, delimiter=";", quotechar="'", lineterminator="\n")
writer.writerow(["a;b", "c'd", " plain"])
writer.writerow(["x", "", "z"])
text = buffer.getvalue()
print(repr(text))

reader = csv.reader(io.StringIO(text), delimiter=";", quotechar="'", skipinitialspace=True)
for row in reader:
    print(row)

tab = io.StringIO()
writer = csv.writer(tab, dialect="excel-tab", lineterminator="\n")
writer.writerow(["one", "two, three", "four\tfive"])
tab_text = tab.getvalue()
print(repr(tab_text))
print(next(csv.reader(io.StringIO(tab_text), dialect="excel-tab")))
