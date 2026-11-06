"""Cases for text_wrap (see spec.md). cases(rng) -> (public, hidden, perf). Width and text on stdin."""

STDIN = True

LETTERS = 'abcdefghijklmnopqrstuvwxyz'

COMMON = ('the quick brown fox jumps over lazy dog and to of a in that is for it with as was on be at '
          'by this had not are but from or have an they which one you were her all she there would '
          'their we him been has when who will more no if out so said what up its about').split()


def word(rng):
    r = rng.randrange(1000)
    if r < 600:
        return COMMON[rng.randrange(len(COMMON))]
    if r < 980:
        n = rng.randrange(1, 14)
        return ''.join(LETTERS[rng.randrange(26)] for _ in range(n))
    n = rng.randrange(20, 120)
    return ''.join(LETTERS[rng.randrange(26)] for _ in range(n))


def paragraph(rng, nwords):
    parts = []
    for i in range(nwords):
        if i:
            r = rng.randrange(100)
            if r < 95:
                parts.append(' ')
            elif r < 98:
                parts.append('\t')
            else:
                parts.append('\n')
        parts.append(word(rng))
    return ''.join(parts)


def text(rng, nparagraphs, blank='\n\n'):
    paras = [paragraph(rng, rng.randrange(1, 70)) for _ in range(nparagraphs)]
    return blank.join(paras)


def with_width(w, body):
    return ('%d\n' % w).encode() + body.encode()


def public_cases():
    basic = with_width(40, (
        'The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs.\n'
        'A second line of the same paragraph joins the first one.\n'
        '\n'
        'Short one.\n'
        '\n'
        'A third paragraph here with several words in it.\n'))
    long_word_spaces = with_width(10, (
        'alpha beta gamma delta\n'
        '   \n'
        '\n'
        'supercalifragilisticexpialidocious the end\n'
        '  \t \n'
        'omega psi chi\n'))
    bad_width = b'9\nhello world\n'
    return [
        ('basic', basic, []),
        ('long_word_spaces', long_word_spaces, []),
        ('bad_width', bad_width, []),
    ]


def hidden_cases(rng):
    w10 = with_width(10, text(rng, 8))
    w200 = with_width(200, text(rng, 6))

    exact = ('x' * 25)
    body = 'one two %s three four\n\nshort words only here\n\na %s b\n' % (exact, exact)
    exact_word = with_width(25, body)

    tabs_body = ('a\tb\tc\td\te\n'
                 '\t\t\t\n'
                 'longer words here\tand\tthere\n'
                 '   \n'
                 '\t\n'
                 'tail\twords\n')
    tabs = with_width(12, tabs_body)

    no_final = with_width(30, text(rng, 5))

    mixed = with_width(rng.randrange(10, 201), text(rng, 7, blank='\n   \n\n'))

    return [
        ('w10', w10, []),
        ('w200', w200, []),
        ('exact_word', exact_word, []),
        ('tabs', tabs, []),
        ('no_final_newline', no_final, []),
        ('mixed', mixed, []),
    ]


def perf_case(rng):
    """About 60 MiB: one ~1 MiB block of paragraphs, repeated 60 times."""
    w = 72
    target = 1 << 20
    parts = []
    size = 0
    while size < target:
        para = paragraph(rng, rng.randrange(10, 160))
        parts.append(para)
        parts.append('\n\n')
        size += len(para) + 2
    block = ''.join(parts).encode()
    return ('perf', b'%d\n' % w + block * 60, [])


def cases(rng):
    public = public_cases()
    hidden = hidden_cases(rng)
    perf = perf_case(rng)
    return public, hidden, perf
