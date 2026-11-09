"""Cases for dsl_calc (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def txt(s):
    return s.encode('utf8')


def cases(rng):
    public = [
        ('basic', txt("""push 2
push 3
add
print
push 10
sub
print
push 4
mul
print
"""), []),
        ('stack_ops', txt("""push 1
push 2
swap
print
dup
add
store x
load x
print
drop
print
drop
print
"""), []),
        ('errors', txt("""add
push x
push 2147483648
store a
push 5
store a
load b
load a
print
swap
push 1
push 2
push 3
add extra
frobnicate
"""), []),
        ('comments', txt("""# start
   push 7   
    # indented comment
print
"""), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('whitespace', b'\n \t\n# c\n', []),
        ('int64_edges', txt("""push 9223372036854775807
push 1
add
push -9223372036854775808
print
push 1
sub
push 9223372036854775807
push -1
mul
print
"""), []),
        ('overflow_keeps_operands', txt("""push 9223372036854775807
push 1
add
print
stack
"""), []),
        ('leading_zeros', txt("push 0007\npush -000\nprint\nprint\n"), []),
        ('plus_sign', txt("push +5\npush 5\nadd\n"), []),
        ('unicode_names', txt("push 4\nstore café\nload café\nload 日本\n"), []),
        ('crlf', b'push 1\r\npush 2\r\nadd\r\nprint\r\n', []),
        ('clear_final', b'push 1\npush 2\nclear\n', []),
        ('missing_args', b'push\nstore\nload\nadd 1\n', []),
    ]
    for k in range(4):
        lines = []
        for _ in range(rng.randrange(20, 300)):
            r = rng.random()
            if r < 0.35:
                lines.append('push %d' % rng.randrange(-10 ** 12, 10 ** 12))
            elif r < 0.55:
                lines.append(rng.choice(['add', 'sub', 'mul']))
            elif r < 0.65:
                lines.append(rng.choice(['dup', 'swap', 'drop', 'print', 'clear']))
            elif r < 0.75:
                lines.append('store v%d' % rng.randrange(5))
            elif r < 0.85:
                lines.append('load v%d' % rng.randrange(5))
            elif r < 0.92:
                lines.append('push %s' % rng.choice(['x', '1x', '+1', '']))
            else:
                lines.append('# comment')
        hidden.append(('random%d' % k, txt('\n'.join(lines) + '\n'), []))
    perf = ('perf', txt('\n'.join('push %d\nadd' % i for i in range(200000)) + '\n'), [])
    return public, hidden, perf
