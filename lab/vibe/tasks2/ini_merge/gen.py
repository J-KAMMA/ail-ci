"""Cases for ini_merge (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def txt(s):
    return s.encode('utf8')


def cases(rng):
    public = [
        ('basic', txt("""# global config
name = demo
[server]
host=example.org
port = 8080
[client]
retries=3
server=example.org
"""), []),
        ('overrides', txt("""a=1
[sec]
k=first
k=second
[sec]
j=x=y=z
"""), []),
        ('errors', txt("""[good]
ok=1
[broken
nokey
=novalue
bad key=1
[empty]
[other]
; comment
  # indented comment
value with = equals
"""), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_only', b'\n \n\t\n', []),
        ('crlf', b'[a]\r\nx=1\r\ny = 2 \r\n', []),
        ('default_section', b'a=1\nb=2\n[s]\nc=3\n', []),
        ('empty_values', b'[s]\na=\nb=\n=', []),
        ('unicode', '[kaffe]\nnamé=café\n日本=語\n'.encode('utf8'), []),
        ('only_section', b'[solo]\n', []),
        ('duplicate_sections', b'[s]\na=1\n[t]\na=2\n[s]\na=3\n', []),
        ('no_final_newline', b'[s]\na=1', []),
        ('spaces_in_value', b'[s]\na=  hello world  \n', []),
    ]
    keys = ['k%02d' % i for i in range(20)]
    for k in range(4):
        lines = []
        for _ in range(rng.randrange(20, 200)):
            r = rng.random()
            if r < 0.2:
                lines.append('[sec%d]' % rng.randrange(10))
            elif r < 0.35:
                lines.append('%s=%d' % (rng.choice(keys), rng.randrange(10000)))
            elif r < 0.45:
                lines.append('bad line')
            elif r < 0.55:
                lines.append('# comment %d' % rng.randrange(100))
            else:
                lines.append('%s = value %d' % (rng.choice(keys), rng.randrange(100)))
        hidden.append(('random%d' % k, txt('\n'.join(lines) + '\n'), []))
    perf = ('perf', txt('\n'.join('[s%d]\n%s' % (i % 100, '\n'.join('%s=%d' % (k, i) for k in keys))
                                  for i in range(5000)) + '\n'), [])
    return public, hidden, perf
