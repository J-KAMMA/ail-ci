"""Source-free JSON query graph checked against Python's lexical JSON parser."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import test_ail_c_objects as support


LIBRARIES = ('json_text', 'json_document', 'json_tree', 'json_pointer',
             'string_map', 'json_string_map')
CLIENT = r'''fn main() -> int {
 let nodes = json_parse_document(read_bytes(sys.argv[1]).decode());
 let pointer: str = read_bytes(sys.argv[2]).decode();
 let index: int = json_pointer_index(nodes, pointer);
 let segments: list[str] = json_pointer_segments(pointer);
 let subtree = json_subtree(nodes, index);
 let extracted = json_pointer_extract(nodes, pointer);
 let values: dict[str,str] = json_string_map_at(nodes, pointer);
 let parsed: dict[str,str] = json_string_map_parse(read_bytes(sys.argv[3]).decode());
 let keys: list[str] = values.keys(); let items: list[str] = values.values();
 write_stdout_bytes((str(json_validate_nodes(nodes)) + "\n" + str(index) + "\n").encode());
 write_stdout_bytes((json_render_document(nodes) + "\n").encode());
 write_stdout_bytes((json_quote("\x00".join(segments)) + "\n").encode());
 write_stdout_bytes((string_map_render(values) + string_map_render(parsed)).encode());
 nodes[index].key = "changed"; nodes[index].kind = 0; nodes[index].text = "null";
 nodes[0].kind = 0; nodes[0].text = "null"; nodes = [];
 values.clear(); values = {}; parsed.clear();
 let churn = json_parse_document("{\"churn\":[1,true,null,\"new\"]}");
 let churn_map: dict[str,str] = json_string_map_parse("{\"churn\":\"new\"}");
 write_stdout_bytes((json_render_document(subtree) + "\n").encode());
 write_stdout_bytes((json_render_document(extracted) + "\n").encode());
 write_stdout_bytes((str(subtree[0].parent) + "\n" + json_quote(subtree[0].key) + "\n").encode());
 write_stdout_bytes((json_quote("\x00".join(keys)) + "\n" + json_quote("\x00".join(items)) + "\n").encode());
 let caught: int = 0;
 let missing = json_parse_document("{\"a\":[]}");
 try { json_pointer_index(missing, "/absent"); } except KeyError { caught += 1; }
 try { json_pointer_index(missing, "/a/99999999999999999999999999999999999"); } except KeyError { caught += 1; }
 try { json_pointer_index(missing, "/a/-"); } except KeyError { caught += 1; }
 let invalid: list[str] = ["a", "/~", "/~2", "/a/01", "/a/+1"];
 for path in invalid { try { json_pointer_index(missing, path); } except ValueError { caught += 1; } }
 let duplicate = json_parse_document("{\"a\":\"x\",\"a\":\"y\"}");
 try { json_pointer_index(duplicate, "/a"); } except ValueError { caught += 1; }
 try { json_string_map_parse("{\"a\":1}"); } except ValueError { caught += 1; }
 try { json_string_map_parse("[]"); } except ValueError { caught += 1; }
 let malformed = [];
 malformed.append(JsonValue(5, -1, "", ""));
 malformed.append(JsonValue(3, 7, "a", "x"));
 try { json_validate_nodes(malformed); } except ValueError { caught += 1; }
 try { json_render_document(malformed); } except ValueError { caught += 1; }
 try { json_subtree(malformed, 0); } except ValueError { caught += 1; }
 write_stdout_bytes((str(caught) + "\n" + str(json_scalar_kind("-12.50e+09")) + "\n").encode());
 let scalars: list[str] = ["null", "true", "false", "-0.000e+999999", "\"日本語\\u0000😀\"", "[null,{}]"];
 for text in scalars { let scalar = json_parse_document(text); write_stdout_bytes((json_render_document(scalar) + "\n").encode()); }
 if caught != 14 { return 8; } return 0;
}'''


class Pairs(list):
    """An object, retaining duplicate members and their original order."""


class Number(str):
    """A numeric token, retaining its spelling without finite-width conversion."""


def parse(text):
    return json.loads(text, object_pairs_hook=Pairs, parse_int=Number, parse_float=Number)


def compact(value):
    if isinstance(value, Number):
        return str(value)
    if isinstance(value, Pairs):
        return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + compact(v)
                              for k, v in value) + '}'
    if isinstance(value, list):
        return '[' + ','.join(map(compact, value)) + ']'
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def preorder(value):
    result = []

    def visit(item, parent=-1, key=''):
        index = len(result)
        result.append((item, parent, key))
        if isinstance(item, Pairs):
            for name, child in item:
                visit(child, index, name)
        elif isinstance(item, list):
            for child in item:
                visit(child, index)
    visit(value)
    return result


def expected(document, pointer, standalone):
    root = parse(document)
    segments = [] if pointer == '' else [part.replace('~1', '/').replace('~0', '~')
                                         for part in pointer[1:].split('/')]
    selected = root
    for segment in segments:
        if isinstance(selected, Pairs):
            matches = [value for key, value in selected if key == segment]
            if len(matches) != 1:
                raise ValueError('oracle needs an unambiguous pointer')
            selected = matches[0]
        else:
            selected = selected[int(segment)]
    nodes = preorder(root)
    index = next(i for i, (item, _, _) in enumerate(nodes) if item is selected)
    values, parsed = dict(selected), dict(parse(standalone))
    quote = lambda text: json.dumps(text, ensure_ascii=False, separators=(',', ':'))
    lines = ['1', str(index), compact(root), quote('\0'.join(segments)),
             compact(Pairs(values.items())), compact(Pairs(parsed.items())),
             compact(selected), compact(selected), '-1', '""',
             quote('\0'.join(values)), quote('\0'.join(values.values())), '14', '2',
             'null', 'true', 'false', '-0.000e+999999', quote('日本語\0😀'), '[null,{}]']
    return ('\n'.join(lines) + '\n').encode()


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class ObjectJsonQueryTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot

    def relocated(self):
        originals = [support.ROOT / 'language_examples' / (name + '.ail') for name in LIBRARIES]
        pins = list(map(pin, originals))
        sources, objects = self.root / '元の JSON sources', self.root / '元の JSON objects'
        sources.mkdir(); objects.mkdir()
        built = []
        for original in originals:
            source = sources / original.name
            source.write_text('\n'.join(line for line in original.read_text(encoding='utf8').splitlines()
                                        if not line.strip().startswith('use ')), encoding='utf8')
            obj = objects / (original.stem + '.o')
            result = self.command('compile-module', source,
                                  *(arg for dependency in built for arg in ('--object', dependency)), '-o', obj)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            source.unlink(); built.append(obj)
        moved = self.root / '移動した JSON query objects'; moved.mkdir()
        for i, obj in enumerate(built):
            target = moved / obj.name
            obj.rename(target); Path(str(obj) + '.json').rename(Path(str(target) + '.json'))
            built[i] = target
        sources.rmdir(); objects.rmdir()
        self.assertFalse(list(self.root.rglob('*.ail')))
        self.assertEqual(list(map(pin, originals)), pins)
        return tuple(built), originals, pins

    def test_moved_source_free_graph_inverse_relinks_complete_lexical_json(self):
        objects, originals, pins = self.relocated()
        before = self.snapshot(*objects)
        descriptors = [json.loads(Path(str(obj) + '.json').read_bytes())['contract'] for obj in objects]
        self.assertTrue(all(contract['version'] == 11 for contract in descriptors))
        self.assertEqual(descriptors[2]['exports']['json_subtree']['result'], 'struct_list:JsonValue')
        self.assertEqual(descriptors[3]['exports']['json_pointer_segments']['result'], 'slist')
        self.assertEqual(descriptors[5]['exports']['json_string_map_at']['result'], 'smap')
        paths = [self.root / name for name in ('入力 JSON.txt', '選択 pointer.txt', '別の map.txt')]
        huge = '7' * 4097 + '.000e+999999'
        special = Pairs([('', ''), ('日本語\0😀', '値\0𐀀'), ('dup', 'first'), ('dup', 'last')])
        cases = [(compact(special), '', compact(special)),
                 ('{"scalar":[null,true,false,' + huge + '],"target":{"x":"v"},"dup":1,"dup":2}',
                  '/target', '{"a":"old","a":"last"}'),
                 ('{"a/b":{"~key":{"~1":"once","":"empty"}}}', '/a~1b/~0key', '{}'),
                 ('{"~1":{"once":"decoded once"}}', '/~01', '{}'),
                 ('{"array":[0,{"map":{"x":"y"}}]}', '/array/1/map', '{}'),
                 (compact(Pairs([('長' * 65537, '😀' * 65537)])), '', '{}')]
        cases += [(compact(Pairs((f'鍵😀{i}', f'値\0{i}') for i in range(n))), '', '{}')
                  for n in (8191, 8192, 8193)]
        for order in (objects, tuple(reversed(objects))):
            exe = self.ail_build('query_' + str(order[0] == objects[0]), CLIENT, *order)
            self.assertFalse(list(self.root.rglob('*.ail')))
            for document, pointer, standalone in cases:
                for path, text in zip(paths, (document, pointer, standalone)):
                    path.write_bytes(text.encode())
                input_pins = list(map(pin, paths))
                result = subprocess.run([str(exe), *map(str, paths)], capture_output=True, timeout=180)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, expected(document, pointer, standalone), b''))
                self.assertEqual(list(map(pin, paths)), input_pins)
        self.assertEqual(self.snapshot(*objects), before)
        self.assertEqual(list(map(pin, originals)), pins)

    def test_invalid_metadata_kinds_structs_dependencies_and_calls_before_artifact(self):
        objects, originals, pins = self.relocated()
        before = self.snapshot(*objects)
        descriptor = Path(str(objects[-1]) + '.json'); saved = descriptor.read_bytes()
        envelope = json.loads(saved)
        variants = []
        for field, value in (('version', 12), ('dependencies', [{'abi': 'bad', 'object_sha256': '0' * 64}])):
            changed = copy.deepcopy(envelope); changed['contract'][field] = value; variants.append(changed)
        changed = copy.deepcopy(envelope)
        changed['contract']['exports']['json_string_map_at']['result'] = 'dict[str,bytes]'
        variants.append(changed)
        try:
            for i, changed in enumerate(variants):
                descriptor.write_text(json.dumps(changed), encoding='utf8')
                self.refused('metadata_' + str(i), CLIENT, objects)
        finally:
            descriptor.write_bytes(saved)
            os.utime(descriptor, ns=(descriptor.stat().st_atime_ns, before[-1][1]))
        descriptor = Path(str(objects[1]) + '.json'); saved = descriptor.read_bytes()
        try:
            changed = json.loads(saved)
            changed['contract']['structs']['JsonValue']['fields'][0][1] = 'smap'
            descriptor.write_text(json.dumps(changed), encoding='utf8')
            self.refused('struct_metadata', CLIENT, objects)
        finally:
            descriptor.write_bytes(saved)
            os.utime(descriptor, ns=(descriptor.stat().st_atime_ns, before[3][1]))
        self.refused('missing_dependency', CLIENT, objects[1:])
        for i, source in enumerate((
            'fn main() -> int { let x = json_pointer_index("bad", ""); return 0; }',
            'fn main() -> int { let n = json_parse_document("{}"); let x = json_pointer_extract(n, 1); return 0; }',
            'fn main() -> int { let x: dict[str,int] = json_string_map_parse("{}"); return 0; }',
        )):
            self.refused('kind_' + str(i), source, objects)
        self.assertEqual(self.snapshot(*objects), before)
        self.assertEqual(list(map(pin, originals)), pins)

    def refused(self, name, text, objects):
        source = self.write(name + '.ail', text); output = self.root / name
        result = self.command('compile', source,
                              *(arg for obj in objects for arg in ('--object', obj)), '-o', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'Traceback', result.stderr)
        for suffix in ('', '.exe', '.o', '.json', '.o.json'):
            self.assertFalse(Path(str(output) + suffix).exists())
        source.unlink()


if __name__ == '__main__':
    unittest.main()
