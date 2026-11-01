import csv
import io


def dump(quoting, escapechar=None):
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=quoting, escapechar=escapechar)
    writer.writerow(["a,b", 'quote"here', "plain", ""])
    return buffer.getvalue()


print(repr(dump(csv.QUOTE_ALL)))
print(repr(dump(csv.QUOTE_NONE, "\\")))
print(repr(dump(csv.QUOTE_MINIMAL)))
print(repr(dump(csv.QUOTE_MINIMAL, "\\")))
