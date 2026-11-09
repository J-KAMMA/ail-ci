"""Cases for todo_file (see spec.md). cases(rng) -> (public, hidden, perf)."""
A = ['{input}']


def text(lines):
    return ('\n'.join(lines) + '\n').encode('utf8')


def cases(rng):
    public = [
        ('basic', text([
            'add 2 write tests',
            'add 1 buy milk',
            'add 3 send mail',
            'list',
            'done 1',
            'show 1',
            'show 2',
            'list',
            'stats',
            'remove 2',
            'list',
            'stats',
        ]), A),
        ('errors', text([
            'add 1 first',
            'add 1 second',
            'add 0 zero',
            'add x bad',
            'add 4',
            'done 9',
            'done 1',
            'done 1',
            'remove 4',
            'show nope',
            'list now',
            'stats extra',
            'wat 1',
            'list',
            'stats',
        ]), A),
        ('unicode', text([
            'add 5 café au lait',
            'add 6 日本語のテキスト',
            'add 7 two  spaces',
            'add 8 tab\there',
            'show 6',
            'list',
            'stats',
        ]), A),
    ]
    hidden = [
        ('empty', b'', A),
        ('only_newlines', b'\n\n\n', A),
        ('no_final_newline', b'add 1 a\nlist\nadd 2 b', A),
        ('crlf_text', b'add 1 hi\r\nshow 1\nstats\n', A),
        ('reuse_after_remove', text([
            'add 4 old',
            'remove 4',
            'add 4 new',
            'done 4',
            'remove 4',
            'add 4 again',
            'show 4',
            'stats',
        ]), A),
        ('id_edges', text([
            'add 2147483647 max',
            'add 2147483648 toobig',
            'add 0007 seven',
            'show 7',
            'show 2147483647',
            'stats',
        ]), A),
        ('sort_numeric', text(['add 10 ten'] + ['add %d v%d' % (i, i) for i in (2, 100, 9, 1, 33)] + ['list']), A),
        ('empty_text_trailing', text(['add 1 ', 'add 2 x ', 'add 3  y', 'show 2', 'show 3', 'stats']), A),
        ('unicode_len', text(['add 1 éé', 'add 2 😀😀😀', 'stats']), A),
    ]
    for k in range(4):
        lines = []
        for _ in range(rng.randrange(20, 200)):
            r = rng.random()
            if r < 0.45:
                lines.append('add %d %s' % (rng.randrange(1, 60), 'item %d' % rng.randrange(1000)))
            elif r < 0.6:
                lines.append('done %d' % rng.randrange(1, 60))
            elif r < 0.7:
                lines.append('remove %d' % rng.randrange(1, 60))
            elif r < 0.8:
                lines.append('show %d' % rng.randrange(1, 60))
            elif r < 0.9:
                lines.append('list')
            else:
                lines.append('stats')
        hidden.append(('random%d' % k, text(lines), A))
    perf = ('perf', text(['add %d x' % i for i in range(1, 20000)] + ['list', 'stats']), A)
    return public, hidden, perf
