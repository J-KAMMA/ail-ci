"""utf8_stream's incremental decoder, feed by feed, against an independent model of its contract.

Random byte streams (valid text, truncated characters, overlong forms, surrogates, stray
continuation bytes, invalid leads) are cut into random chunks. For every feed the AIL decoder must
return the same text as the model, or fail on the same feed. The model is the original
whole-buffer algorithm (scan every byte, reject an invalid sequence -- including an unfinished one
whose first continuation byte already rules it out -- as soon as it is visible, then strict-decode
the complete prefix), written here in Python. CPython's own incremental decoder is stricter about
nothing but waits one feed longer before rejecting such prefixes, so it is not the reference.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''use utf8_stream;
fn main() -> int {
    let decoder = utf8_decoder_new();
    let index: int = 0;
    try {
        for chunk in file_chunks(sys.argv[1], int(sys.argv[2])) {
            let text: str = utf8_decode_feed(decoder, chunk);
            print(str(index) + ":" + str(len(text)) + ":" + text.encode("utf-8").hex());
            index += 1;
        }
        utf8_decode_finish(decoder);
        print("end");
    } except ValueError {
        print(str(index) + ":error");
    }
    return 0;
}'''

PIECES = ['a', 'Z', '\n', 'é', '日', '😀', '\u0085', '߿', '￿', '\U0010ffff']
BAD = [b'\x80', b'\xbf', b'\xc0\xaf', b'\xc1\xbf', b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf0\x80\x80\x80',
       b'\xf4\x90\x80\x80', b'\xf5', b'\xff', b'\xe6', b'\xf0\x9f', b'\xe6\x97']


def _complete_length(data):
    """Bytes up to the last character boundary; ValueError on any visibly invalid sequence."""
    position = 0
    while position < len(data):
        lead = data[position]
        if lead <= 127:
            position += 1
            continue
        if 194 <= lead <= 223:
            width = 2
        elif 224 <= lead <= 239:
            width = 3
        elif 240 <= lead <= 244:
            width = 4
        else:
            raise ValueError
        remaining = len(data) - position
        for i in range(1, min(width, remaining)):
            byte = data[position + i]
            if byte < 128 or byte > 191:
                raise ValueError
            if i == 1 and ((lead == 224 and byte < 160) or (lead == 237 and byte > 159)
                           or (lead == 240 and byte < 144) or (lead == 244 and byte > 143)):
                raise ValueError
        if remaining < width:
            return position
        position += width
    return position


def expected(data, size):
    pending = b''
    lines = []
    chunks = [data[i:i + size] for i in range(0, len(data), size)]
    for index, chunk in enumerate(chunks):
        combined = pending + chunk
        try:
            complete = _complete_length(combined)
            text = combined[:complete].decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            return lines + ['%d:error' % index]
        pending = combined[complete:]
        lines.append('%d:%d:%s' % (index, len(text), text.encode('utf-8').hex()))
    return lines + (['%d:error' % len(chunks)] if pending else ['end'])


class Utf8StreamFuzz(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_matches_cpython_incremental_decoder(self):
        program = build(self, 'utf8_stream_fuzz', SOURCE, modules=('utf8_stream',))
        rng = random.Random(20261011)
        failures = []
        for case in range(600):
            parts = []
            for _ in range(rng.randrange(0, 12)):
                if rng.random() < 0.15:
                    parts.append(rng.choice(BAD))
                else:
                    parts.append(rng.choice(PIECES).encode('utf-8'))
            data = b''.join(parts)
            size = rng.choice([1, 2, 3, 4, 5, 7, 16])
            path = self.root / 'case.bin'
            path.write_bytes(data)
            result = subprocess.run([str(program), str(path), str(size)], capture_output=True, timeout=30)
            got = result.stdout.decode().splitlines()
            want = expected(data, size)
            if got != want:
                failures.append('%r size=%d: want %r got %r' % (data, size, want, got))
        self.assertFalse(failures, '\n'.join(failures[:10]) + '\n(%d failures)' % len(failures))


if __name__ == '__main__':
    unittest.main()
