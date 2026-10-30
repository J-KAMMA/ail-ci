"""Cases for echo_pack (see spec.md). cases(rng) -> (public, hidden, perf). Data on standard input."""
import importlib.util
from pathlib import Path

STDIN = True
HERE = Path(__file__).resolve().parent


def ref():
    spec = importlib.util.spec_from_file_location('echo_pack_ref', HERE / 'reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORDS = ['the', 'packet', 'echo', 'stream', 'of', 'bytes', 'window', 'again', 'and', 'copy', 'literal', 'run',
         'distance', 'zebra', 'quartz', '\n', '. ', ', ', '0', '42', 'xyzzy']


def text(rng, nwords):
    return ' '.join(rng.choice(WORDS) for _ in range(nwords)).encode()


def stream(n, tokens, h):
    return b'EP1' + n.to_bytes(4, 'little') + b''.join(tokens) + h.to_bytes(4, 'little')


def cases(rng):
    r = ref()
    sample = b'abcabcabcabcabc hello hello hello world, abcabc!'
    public = [
        ('pack_sample', sample, ['pack']),
        ('unpack_sample', r.pack(sample), ['unpack']),
        ('unpack_bad_hash', r.pack(sample)[:-1] + bytes([r.pack(sample)[-1] ^ 1]), ['unpack']),
    ]
    # the 8-candidate rule: an old long match is hidden by 8 newer short ones
    hidden_long = b'KEY!' + b'0123456789' * 3 + b'|' + b''.join(b'KEY!' + bytes([65 + k]) for k in range(8)) + b'KEY!0123456789'
    visible_long = b'KEY!' + b'0123456789' * 3 + b'|' + b''.join(b'KEY!' + bytes([65 + k]) for k in range(7)) + b'KEY!0123456789'
    far = b'FARAWAY-PATTERN!' + bytes(rng.randrange(256) for _ in range(65530)) + b'FARAWAY-PATTERN!'
    far2 = b'FARAWAY-PATTERN!' + bytes(rng.randrange(256) for _ in range(65519)) + b'FARAWAY-PATTERN!'
    rnd = bytes(rng.randrange(256) for _ in range(1000))
    lit128 = bytes(range(128)) + b'WXYZWXYZ'
    tie = b'abcdX' + b'abcdY' + b'abcdZ' + b'abcdQ'
    pk = r.pack
    valid_custom = stream(7, [b'\x00a', b'\x00b', b'\x80\x00\x02', b'\x00c'], r.ep_hash(b'abababc'))
    hidden = [
        ('pack_empty', b'', ['pack']),
        ('pack_one_byte', b'x', ['pack']),
        ('pack_four_bytes', b'aaaa', ['pack']),
        ('pack_five_same', b'aaaaa', ['pack']),
        ('pack_zero_run', bytes(1000), ['pack']),
        ('pack_overlap_period3', b'xyz' * 300, ['pack']),
        ('pack_tail_short', b'abcdefgh-abcdefg', ['pack']),
        ('pack_random_bytes', rnd, ['pack']),
        ('pack_literal_128', lit128, ['pack']),
        ('pack_literal_257', bytes(rng.randrange(256) for _ in range(257)), ['pack']),
        ('pack_hidden_long_match', hidden_long, ['pack']),
        ('pack_visible_long_match', visible_long, ['pack']),
        ('pack_distance_limit', far, ['pack']),
        ('pack_distance_just_inside', far2, ['pack']),
        ('pack_tie_largest_p', tie + b'abcd', ['pack']),
        ('pack_max_len_131', b'Q' + bytes(range(200)) + bytes(range(200)), ['pack']),
        ('pack_text', text(rng, 3000), ['pack']),
        ('pack_binary_all_bytes', bytes(range(256)) * 20, ['pack']),
        ('unpack_empty_stream', pk(b''), ['unpack']),
        ('unpack_text', pk(text(rng, 2000)), ['unpack']),
        ('unpack_zero_run', pk(bytes(5000)), ['unpack']),
        ('unpack_random', pk(rnd), ['unpack']),
        ('unpack_custom_valid', valid_custom, ['unpack']),
        ('unpack_overlap_dist1', stream(9, [b'\x00z', b'\x84\x00\x01'], r.ep_hash(b'z' * 9)), ['unpack']),
        ('unpack_empty_input', b'', ['unpack']),
        ('unpack_bad_magic', b'EP2' + pk(b'abc')[3:], ['unpack']),
        ('unpack_short_length', b'EP1\x00\x00', ['unpack']),
        ('unpack_truncated_literal', pk(b'abcdefgh')[:-6], ['unpack']),
        ('unpack_truncated_distance', stream(8, [b'\x00ab', b'\x82\x00'], 0)[:-4], ['unpack']),
        ('unpack_dist_zero', stream(6, [b'\x01ab', b'\x80\x00\x00'], r.ep_hash(b'ababab')), ['unpack']),
        ('unpack_dist_too_far', stream(6, [b'\x01ab', b'\x80\x00\x03'], r.ep_hash(b'ababab')), ['unpack']),
        ('unpack_copy_too_long', stream(5, [b'\x01ab', b'\x80\x00\x02'], r.ep_hash(b'ababa')), ['unpack']),
        ('unpack_literal_too_long', stream(2, [b'\x02abc'], r.ep_hash(b'ab')), ['unpack']),
        ('unpack_missing_hash', pk(b'hello hello')[:-2], ['unpack']),
        ('unpack_trailing_byte', pk(b'hello hello') + b'\x00', ['unpack']),
        ('unpack_length_too_big', b'EP1\x10\x00\x00\x00' + pk(b'abc')[7:], ['unpack']),
        ('unpack_length_zero_with_token', stream(0, [b'\x00a'], 0), ['unpack']),
        ('no_args', b'abc', []),
        ('bad_mode', b'abc', ['Pack']),
        ('two_args', b'abc', ['pack', 'unpack']),
    ]
    for k in range(5):
        data = text(rng, rng.randrange(0, 400)) + bytes(rng.randrange(4) for _ in range(rng.randrange(0, 200)))
        hidden.append(('pack_random%d' % k, data, ['pack']))
        hidden.append(('unpack_random%d' % k, pk(data), ['unpack']))
    for k in range(4):
        s = bytearray(pk(text(rng, rng.randrange(20, 300))))
        i = rng.randrange(7, len(s))
        s[i] ^= 1 << rng.randrange(8)
        hidden.append(('unpack_corrupt%d' % k, bytes(s), ['unpack']))
    perf = ('perf', perf_data(rng), ['pack'])
    return public, hidden, perf


def perf_data(rng, size=32000000):
    vocab = [(''.join(rng.choice('etaoinshrdlcumwfgypbvk') for _ in range(rng.randrange(2, 9)))).encode() for _ in range(2000)]
    parts = []
    total = 0
    choice = rng.choice
    rand = rng.random
    while total < size:
        r = rand()
        if r < 0.9:
            w = choice(vocab) + b' '
        elif r < 0.95:
            w = b'%d,' % rng.randrange(0, 100000)
        elif r < 0.99:
            w = b'\n'
        else:
            w = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 30)))
        parts.append(w)
        total += len(w)
    return b''.join(parts)[:size]
