"""Cases for json_lite (see spec.md). cases(rng) -> (public, hidden, perf)."""
import json

A = []
STDIN = True


def cases(rng):
    public = [
        ('basic', b'{"a": 1, "b": [2, 3]}', A),
        ('empty', b'', A),
        ('scalar', b'-42', A),
    ]
    hidden = [
        ('nested', b'{"a":{"b":[1,{"c":2}]},"d":[3,[4,[5]]]}', A),
        ('ignore_strings', b'{"a":"123","b":4}', A),
        ('escapes', b'{"s":"say \\"hi\\" [1,2] \\\\","n":5}', A),
        ('booleans', b'[true,false,null,1,-2]', A),
        ('whitespace', b' \n\t\r [ 1 , 2 ] \n', A),
        ('negative', b'[-1,-20,30]', A),
        ('single_zero', b'0', A),
        ('empty_containers', b'{} [] [[]] {"a":{}}', A),
        ('tricky_string', b'"123 456"', A),
        ('no_numbers', b'{"a":"x","b":true,"c":null}', A),
        ('number_starts', b'[0,10,100,-100]', A),
        ('escaped_unicode', b'{"s":"\\u0041","n":7}', A),
        ('objects_in_arrays', b'[{"x":1},{"y":[2]} ,{"z":-3}]', A),
        ('zero_only', b'[[0],[0,0],{"a":0}]', A),
        ('large_numbers', b'[9223372036854775807,-9223372036854775807]', A),
    ]
    records = []
    for i in range(150000):
        records.append({'id': i, 'value': rng.randrange(0, 1000), 'name': 'user%d' % (i % 10000),
                        'ok': i % 2 == 0, 'tags': [i % 7, 'tag%d' % (i % 50)]})
    perf = ('perf', json.dumps(records, separators=(',', ':')).encode(), A)
    return public, hidden, perf
