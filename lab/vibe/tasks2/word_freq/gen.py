"""Cases for word_freq (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def cases(rng):
    public = [
        ('basic', b'the quick brown fox jumps over the lazy dog The THE\n', []),
        ('ties', b'beta Alpha alpha Beta gamma\n', []),
        ('separators', b'abc123def  a_b-c!d\ne\n', []),
    ]
    hidden = [
        ('empty', b'', []),
        ('unicode_separators', 'café naïve Ångström 日本語 abc\n'.encode('utf8'), []),
        ('apostrophes', b"don't can't don't won't\n", []),
        ('digits_only', b'12345 67890\n', []),
        ('top20_cutoff', b' '.join(b'w%02d' % i for i in range(30)), []),
        ('repeat_many', b'a ' * 5000 + b'b ' * 4000 + b'c ' * 3000, []),
        ('no_final_newline', b'one two two three three three', []),
        ('mixed_case', b'AAAA aAaA aaAA Aaaa\n', []),
    ]
    alphabet = 'abcdefghijklmnopqrstuvwxyz'
    for k in range(4):
        words = []
        for _ in range(rng.randrange(100, 5000)):
            n = rng.randrange(1, 9)
            words.append(''.join(rng.choice(alphabet + alphabet.upper()) for _ in range(n)))
        hidden.append(('random%d' % k, ' '.join(words).encode('ascii'), []))
    perf = ('perf', (' '.join('word%d' % (i % 5000) for i in range(1000000))).encode('ascii'), [])
    return public, hidden, perf
