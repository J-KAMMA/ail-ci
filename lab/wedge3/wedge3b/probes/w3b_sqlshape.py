def normalise(text):
    return ''.join(text.split()).lower()

def split_parts(text):
    parts = []
    cur = []
    for ch in text:
        if ch == ';':
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append(''.join(cur))
    return parts

def fnv(text, value=1469598103934665603):
    for ch in text:
        value = ((value ^ ord(ch)) * 1099511628211) & ((1 << 64) - 1)
    return value

def process(parts, sink):
    for p in parts:
        sink.append(normalise(p))
    return None

rows = ["SELECT c0 FROM t0 WHERE c2 = 'amsterdam';", "DELETE FROM t3 WHERE c0 = 3;"]
text = '\n'.join(rows)
parts = split_parts(text)
sink = []
process(parts, sink)
flat = normalise(text)
print('parts', len(parts), parts[:2])
print('sink', sink)
print('flat', len(flat), fnv(flat))
