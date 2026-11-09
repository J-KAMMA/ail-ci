"""Cases for jsonl_stats (see spec.md). cases(rng) -> (public, hidden, perf)."""
import json

STDIN = True


def line(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def cases(rng):
    public = [
        ('basic', '\n'.join([
            line({'user': 'alice', 'amount': 100, 'tag': 'food'}),
            line({'user': 'bob', 'amount': -20.0}),
            line({'user': 'bob', 'amount': 20, 'tag': 'food'}),
            line({'user': 'alice', 'amount': 5, 'tag': 'travel'}),
            line({'user': 'carol', 'amount': 0, 'tag': 'food', 'extra': 1}),
        ]).encode('utf8'), []),
        ('bad', '\n'.join([
            line({'user': 'a', 'amount': 1}),
            'not json',
            '[]',
            '{"user":"b"}',
            '{"user":"b","amount":true}',
            '{"user":"b","amount":1.5}',
            '{"user":3,"amount":1}',
            '{"user":"b","amount":1,"tag":4}',
            '{"user":"b","amount":9223372036854775808}',
        ]).encode('utf8'), []),
        ('unicode', '\n'.join([
            line({'user': 'josé', 'amount': 1, 'tag': 'café'}),
            line({'user': '日本', 'amount': 2, 'tag': 'café'}),
            line({'user': 'josé', 'amount': 3, 'tag': ''}),
        ]).encode('utf8'), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_lines', b'\n  \n\t\n', []),
        ('int64_edges', '\n'.join([
            line({'user': 'a', 'amount': -9223372036854775808, 'tag': 'min'}),
            line({'user': 'a', 'amount': 9223372036854775807, 'tag': 'max'}),
            line({'user': 'a', 'amount': 1, 'tag': 'max'}),
        ]).encode('utf8'), []),
        ('escapes', b'{"user":"a\\\\b","amount":1,"tag":"x\\ty"}\n', []),
        ('many_users', '\n'.join(line({'user': 'u%02d' % (i % 25), 'amount': i})
                                for i in range(60)).encode('utf8'), []),
        ('crlf', b'{"user":"a","amount":1}\r\n{"user":"b","amount":2,"tag":"t"}\r\n', []),
        ('no_final_newline', b'{"user":"a","amount":1}', []),
        ('empty_tag_and_default', b'{"user":"a","amount":1,"tag":""}\n{"user":"a","amount":2}\n', []),
    ]
    tags = ['', 'food', 'travel', 'café', 'z']
    for k in range(4):
        rows = []
        for _ in range(rng.randrange(20, 400)):
            r = rng.random()
            if r < 0.08:
                rows.append(rng.choice(['bad', '[]', '{"user":"x","amount":true}', '']))
            else:
                obj = {'user': 'u%d' % rng.randrange(30), 'amount': rng.randrange(-10 ** 12, 10 ** 12)}
                if rng.random() < 0.8:
                    obj['tag'] = rng.choice(tags)
                rows.append(line(obj))
        hidden.append(('random%d' % k, '\n'.join(rows).encode('utf8'), []))
    perf = ('perf', '\n'.join(line({'user': 'u%d' % (i % 1000), 'amount': i % 10000, 'tag': 't%d' % (i % 100)})
                              for i in range(200000)).encode('utf8'), [])
    return public, hidden, perf
