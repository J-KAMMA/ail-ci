"""Cases for word_freq (see spec.md). cases(rng) -> (public, hidden, perf)."""

A = []
STDIN = True


def word(number):
    return 'w' + ''.join(chr(97 + int(d)) for d in '%03d' % number)


def words(count):
    return ' '.join(word(i) for i in range(count)).encode() + b'\n'


def cases(rng):
    public = [
        ('basic', b'Hello, hello! WORLD.\n', A),
        ('empty', b'', A),
        ('punctuation_only', b'!!! ... 123 456\n', A),
    ]
    hidden = [
        ('case_fold', b'Apple apple APPLE aPPle\n', A),
        ('ties', b'b b a a c\n', A),
        ('digits_split', b'abc123def 42ghi\n', A),
        ('utf8', b'caf\xc3\xa9 cafe\n', A),
        ('no_final_newline', b'one two two three three three', A),
        ('long_word', (b'a' * 120 + b' ' + b'b' * 10 + b'\n'), A),
        ('more_than_20', words(25), A),
        ('exactly_20', words(20), A),
        ('tie_at_cutoff', ' '.join(word(i) for i in range(24)).encode() + b'\n', A),
        ('counts_order', b'x y y z z z\n', A),
        ('mixed_separators', b'a\tb\nc\rd\x00e f-g_h\n', A),
    ]
    alphabet = [word(i) for i in range(4000)]
    parts = []
    size = 0
    while size < 5 * 1000 * 1000:
        piece = ' '.join(rng.choice(alphabet) for _ in range(12)).encode() + b'.\n'
        parts.append(piece)
        size += len(piece)
    perf = ('perf', b''.join(parts), A)
    return public, hidden, perf
