import html

cases = [
    "&amp;", "&amp", "&ampx", "&notit;", "&notin;",
    "&lt;", "&gt;", "&quot;", "&#x27;", "&AElig;",
    "&AMP;", "&not;it;", "&copy", "&copysr;",
]

for text in cases:
    result = html.unescape(text)
    print(repr(text), repr(result))

print(repr(html.unescape("&amp;&amp;plain")))
print(repr(html.unescape("&lt;&gt;&quot;")))
print(repr(html.unescape("&lt;tag&gt;")))
print(repr(html.unescape("&ampx &amp; &notin;")))
