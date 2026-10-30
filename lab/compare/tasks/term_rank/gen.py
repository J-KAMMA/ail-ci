"""Cases for term_rank (see spec.md). cases(rng) -> (public, hidden, perf). Text on standard input."""

STDIN = True

SAMPLE = b"""The quick brown foxes were running; don't stop the RUNNING foxes!
Well-known x-rays, 2024 and 007 things.
%%
Foxes like classes. Classes like foxes' dens -- and 'tis well-known.
%%
caf\xc3\xa9 caf\xc3\xa9 na\xc3\xafve 12-34 o'clock O'Clock
"""

STOPWORDS = ('an and are as at be but by for from had has have he her his in into is it its not of on or our she so than '
             'that the their them then there these they this to was we were which will with you your').split()
SYLL = ['ka', 'ro', 'mi', 'tes', 'lun', 'ing', 'ss', 'ab', 'zo', 'e', 'qu', 'ight', 'st', 'or', 'an', 'is']


def word(rng):
    w = ''.join(rng.choice(SYLL) for _ in range(rng.randrange(1, 4)))
    r = rng.random()
    if r < 0.15:
        w = w.capitalize()
    elif r < 0.2:
        w = w.upper()
    elif r < 0.25:
        w = w + "'" + rng.choice(['s', 't', 'll', ''])
    elif r < 0.3:
        w = w + '-' + rng.choice(SYLL)
    elif r < 0.33:
        w = str(rng.randrange(0, 10 ** rng.randrange(1, 6)))
    elif r < 0.45:
        w = rng.choice(STOPWORDS)
    elif r < 0.47:
        w = rng.choice(['café', '東京', 'naïve', 'x—y'])
    return w


SEPS = [' ', ' ', ' ', ', ', '. ', '\n', ' -- ', "' ", ' (', ') ', '\t', '; ', '!\n', '\r\n']


def text(rng, ndocs, nwords):
    docs = []
    for _ in range(ndocs):
        docs.append(''.join(word(rng) + rng.choice(SEPS) for _ in range(rng.randrange(0, nwords))))
    sep = rng.choice(['\n%%\n', '\n%%\r\n'])
    return sep.join(docs).encode()


def perf_text(rng):
    vocab = []
    for i in range(60000):
        vocab.append(word(rng) + rng.choice(['', '', 'a', 'o', 'er', 'ing', 's']) + ('' if i % 3 else rng.choice(SYLL)))
    common = [rng.choice(vocab) for _ in range(300)]
    seps = [s.encode() for s in SEPS]
    vocab = [v.encode() for v in vocab]
    common = [c.encode() for c in common]
    parts = []
    choice = rng.choice
    rand = rng.random
    for d in range(12000):
        topic = [choice(vocab) for _ in range(40)]
        words = []
        for _ in range(rng.randrange(200, 1100)):
            r = rand()
            words.append(choice(common) if r < 0.45 else choice(topic) if r < 0.75 else choice(vocab))
            words.append(choice(seps))
        parts.append(b''.join(words))
    return b'\n%%\n'.join(parts) + b'\n'


def cases(rng):
    public = [
        ('sample', SAMPLE, ['3']),
        ('single_doc', b'apple banana apple cherry banana apple\n', ['10']),
        ('bad_k', b'a b c\n', ['0']),
    ]
    hidden = [
        ('empty', b'', ['5']),
        ('only_separator', b'%%\n', ['5']),
        ('separators_only', b'%%\n%%\r\n%%', ['2']),
        ('not_separators', b'alpha\n %%\n%%%\n%% \n%%x\nbeta\n%%\ngamma', ['5']),
        ('cr_separator', b'one two\r\n%%\r\nthree four\r\n', ['5']),
        ('joiners', b"don't won't-stop a-b-c x--y 'tis rock'n'roll -lead trail- a'-b a-'b ''x'' y'' -'- '-'\n", ['20']),
        ('joiner_digits', b"12-34 12'34 1'2 9-9 0-0-0 x1 1x 2024 007 0 00 '99 99'\n", ['20']),
        ('number_terms', b'1 22 333 4444 55555 7 7 7 4444 1000 2000\n', ['10']),
        ('stop_words', ' '.join(STOPWORDS).encode() + b' The THE tHe It\'s wE\n', ['10']),
        ('suffix_rules', b'ring sing bring string wings kings running sss ss bass buss bus gas gases cats cat cats ness\n'
                         b'thing things ings ing aing abcing seing class classes is as us usss loss lose\n', ['40']),
        ('suffix_after_join', b"x-rays it's that's walking-sing o'ring don'ts ITS\n", ['20']),
        ('short_tokens', b'a b c 1 2 x y z I A ab cd 12\n', ['20']),
        ('non_ascii_bytes', b'caf\xc3\xa9 \xff\xfe \x80 \xe6\x9d\xb1\xe4\xba\xac CAF\xc3\x89 \xc3\xa9\xc3\xa9s \xff\xff\xffing\n', ['20']),
        ('control_bytes', b'abc\x00def\x01ghi\x7fjkl\tmno\x0bpqr\x0cstu\rvwx\n', ['20']),
        ('ties_bytewise', b'b a ab aa ba bb a b\n%%\nb a\n', ['10']),
        ('prefix_order', b'abc ab abcd ab abc abcd\n', ['10']),
        ('k_one', SAMPLE, ['1']),
        ('k_leading_zeros', SAMPLE, ['0005']),
        ('k_max', SAMPLE, ['1000']),
        ('k_too_big', SAMPLE, ['1001']),
        ('k_plus', SAMPLE, ['+5']),
        ('k_negative', SAMPLE, ['-5']),
        ('k_empty', SAMPLE, ['']),
        ('k_not_number', SAMPLE, ['5x']),
        ('no_args', SAMPLE, []),
        ('two_args', SAMPLE, ['5', '5']),
        ('empty_docs_between', b'%%\nalpha alpha\n%%\n%%\nbeta\n%%\n', ['3']),
        ('no_final_newline', b'zeta eta zeta\n%%\ntheta zeta', ['5']),
        ('df_effect', b'common rare1 common\n%%\ncommon\n%%\ncommon unique unique unique\n', ['5']),
        ('big_tf', (b'word ' * 5000) + b'\n%%\nword other\n', ['5']),
    ]
    for k in range(10):
        hidden.append(('random%d' % k, text(rng, rng.randrange(1, 8), 80), [str(rng.randrange(1, 12))]))
    perf = ('perf', perf_text(rng), ['25'])
    return public, hidden, perf
