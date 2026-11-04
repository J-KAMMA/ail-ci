import html
import html.entities as E

text = "<b>Tom &amp; Jerry&#39;s</b> &copy; 2026"
print(repr(html.escape(text, quote=False)))
print(repr(html.unescape(text)))

print(E.name2codepoint["copy"], repr(E.entitydefs["copy"]))
print(repr(E.html5["copy;"]), len(E.html5))

encoded = html.escape("<p>a & b</p>")
print(repr(encoded))
print(repr(html.unescape(encoded)))
print(html.unescape("&amp") == "&")
print(repr(html.unescape("&#x41;&#66;&#67;")))
