#!/usr/bin/env python3
"""Many-pattern Aho-Corasick workload: ahocorapy vs ahocorasick_rs (Rust).

W3D_IMPL=python (default) builds an ahocorapy KeywordTree; W3D_IMPL=native uses
ahocorasick_rs.  Both receive the same patterns and text.  Matches are canonicalised to
(start, pattern) pairs, sorted, then reduced to a count and a digest.
"""
import os


def make_patterns(n):
    out = []
    letters = 'abcdefghijklmnopqrstuvwxyz'
    for i in range(n):
        a = i * 17
        ln = 4 + (i % 7)
        s = 'p%03d' % i + ''.join(letters[(a + j * 11) % 26] for j in range(ln))
        out.append(s)
    return out


def make_text(patterns, repeats):
    filler = ('pppppppx' * 24)
    return filler * repeats + ' ' + ' '.join(patterns)


def fnv_pair(h, start, word):
    for b in ('%d:%s' % (start, word)).encode('utf-8'):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def main():
    np = int(os.environ.get('W3D_PATTERNS', '500'))
    nt = int(os.environ.get('W3D_REPEATS', '25000'))
    impl = os.environ.get('W3D_IMPL', 'python')
    patterns = make_patterns(np)
    path = os.environ.get('W3D_TEXT')
    if path:
        with open(path, 'r', encoding='ascii') as fh:
            text = fh.read()
    else:
        text = make_text(patterns, nt)
    if impl == 'native':
        import ahocorasick_rs
        ac = ahocorasick_rs.AhoCorasick(patterns)
        raw = ac.find_matches_as_indexes(text, overlapping=True)
        matches = [(start, patterns[idx]) for idx, start, _end in raw]
    else:
        from ahocorapy.keywordtree import KeywordTree
        kt = KeywordTree(case_insensitive=False)
        for p in patterns:
            kt.add(p)
        kt.finalize()
        matches = [(start, word) for word, start in kt.search_all(text)]
    matches.sort()
    h = 0xcbf29ce484222325
    for start, word in matches:
        h = fnv_pair(h, start, word)
    print('patterns=%d repeats=%d textlen=%d matches=%d hash=%016x first=%s last=%s'
          % (np, nt, len(text), len(matches), h,
             matches[0] if matches else None, matches[-1] if matches else None))


if __name__ == '__main__':
    main()
