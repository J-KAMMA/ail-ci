import html

cases = [
    "&#65;", "&#x41;", "&#X41", "&#65", "&#x41",
    "&#00065;", "&#x000041;", "&#x4a;", "&#X4A;",
    "&#233;", "&#xE9;", "&#x00e9",
]

for text in cases:
    print(repr(text), repr(html.unescape(text)))

print(repr(html.unescape("A&#66;C")))
print(repr(html.unescape("&#65;&#66;&#67;")))
print(repr(html.unescape("&#x41;&#X42;&#67")))
print(repr(html.unescape("start &#32; end")))
