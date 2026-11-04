import html

cases = [
    "no references here",
    "a & b",
    "&;",
    "&#;",
    "&#x;",
    "&&",
    "&amp" + "x" * 40,
    "name\twith\ttabs &amp; here",
    "line\nbreak &lt; feed\fhere",
    "&amp;&lt;&gt;",
    "&" * 5,
]

for text in cases:
    print(repr(text), repr(html.unescape(text)))

print(repr(html.unescape("")))
