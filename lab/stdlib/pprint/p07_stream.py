import io
import pprint

data = {"first": [1, 2, 3], "second": {"a": "x", "b": "y"}}

buf = io.StringIO()
printer = pprint.PrettyPrinter(stream=buf, width=25)
printer.pprint(data)
print(repr(buf.getvalue()))

other = io.StringIO()
pprint.pprint(data, stream=other, width=30, indent=2)
print(repr(other.getvalue()))

third = io.StringIO()
pprint.PrettyPrinter(stream=third, compact=True, width=20).pprint([1, 2, 3, 4])
print(repr(third.getvalue()))
