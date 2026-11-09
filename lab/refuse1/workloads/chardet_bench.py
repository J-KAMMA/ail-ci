"""chardet detection vs charset-normalizer on the same byte payloads.

CPython and hybrid both use chardet, so their stdout must match byte for byte.
charset-normalizer (a compiled rewrite) is the separate fast baseline.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _impl import LCG, impl, load_hybrid  # noqa: E402

SAMPLES = 600
WORDS = ['the', 'quick', 'brown', 'fox', 'jumps', 'over', 'lazy', 'dog', 'café', 'naïve',
         '日本語', '测试', '한국어', 'данные', 'αβγδε', 'данные', 'mañana', 'über']


def text_for(rng, n):
    return ' '.join(WORDS[rng.below(len(WORDS))] for _ in range(n)) + '\n'


def payloads():
    rng = LCG(777001)
    out = []
    codecs = ['utf-8', 'shift_jis', 'gb2312', 'euc-kr', 'utf-16', 'big5']
    for i in range(SAMPLES):
        codec = codecs[i % len(codecs)]
        try:
            data = text_for(rng, 40 + rng.below(120)).encode(codec, 'replace')
        except Exception:
            data = b'plain ascii fallback text\n'
        out.append(data)
    return out


def digest(rows):
    h = hashlib.sha256()
    for enc, conf in rows:
        h.update(('%s:%.3f\n' % (enc, conf)).encode('utf-8', 'replace'))
    return h.hexdigest()[:16]


def main():
    mode = impl()
    data = payloads()
    if mode == 'rust':
        from charset_normalizer import from_bytes
        rows = []
        for blob in data:
            best = from_bytes(blob).best()
            rows.append((best.encoding if best is not None else 'none',
                         best.percent_chaos if best is not None else 0.0))
        print('digest', digest(rows), 'samples', len(rows))
        return

    if mode == 'hybrid':
        ud = load_hybrid('universaldetector')
        Detector = ud.UniversalDetector
    else:
        import chardet
        Detector = chardet.UniversalDetector

    rows = []
    for blob in data:
        d = Detector()
        d.feed(blob)
        res = d.close()
        rows.append((res.get('encoding') or 'none', res.get('confidence') or 0.0))
    print('digest', digest(rows), 'samples', len(rows))


if __name__ == '__main__':
    main()
