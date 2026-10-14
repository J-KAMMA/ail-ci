"""Batch pointers preserve an independent JSON oracle and input ownership."""
import json
import os
import shutil
import subprocess
import unittest
import test_ail_c_objects as support
from test_json_query_cli import document, render, selected

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'), 'installed C compiler required')
class JsonPointerBatchTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write

    def test_order_lexemes_errors_and_owned_results(self):
        source = self.write('batch.ail', '''use json_pointer_batch;
fn main()->int {
 let nodes:list[JsonValue]=json_parse_document(read_bytes(sys.argv[1]).decode());
 let requests:list[JsonValue]=json_parse_document(read_bytes(sys.argv[2]).decode());
 let pointers:list[str]=[];
 for i in range(1,len(requests)) {pointers.append(requests[i].text);}
 let before:str=json_render_document(nodes);
 try {
  let values:list[str]=json_pointer_batch(nodes,pointers);
  let output:str=json_pointer_batch_render(nodes,pointers);
  if json_render_document(nodes)!=before {return 4;}
  let again:list[str]=json_pointer_batch(nodes,pointers);
  nodes.clear();pointers.clear();requests.clear();again.clear();
  write_stdout_bytes((output+"\\n"+"["+",".join(values)+"]\\n").encode());return 0;
 } except ValueError {
  if json_render_document(nodes)!=before {return 4;}
  write_stdout_bytes((",".join(pointers)).encode());return 2;
 } except KeyError {
  if json_render_document(nodes)!=before {return 4;}
  write_stdout_bytes((",".join(pointers)).encode());return 3;
 }
}''')
        exe = self.root / 'batch'
        result = self.command('compile', source, '-I', support.ROOT / 'language_examples', '-o', exe)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        if not exe.exists():
            exe = exe.with_suffix('.exe')
        data = ('{"a/b":{"~":{"": [-0.00e+02,9007199254740993,"日本😀\\u0000"]}},'
                '"dup":1,"dup":2,"items":[' + ','.join(
                    '{"n":' + str((1 << 53) + i * 37) + ',"s":"item-' + str(i) + '"}'
                    for i in range(1025)) + ']}').encode()
        value = document(data)
        input_path, pointer_path = self.root / 'document.json', self.root / 'pointers.json'
        input_path.write_bytes(data)
        cases = [[], ['', '/a~1b/~0//0', '/a~1b/~0//1', '/a~1b/~0//2', '/a~1b/~0//1'],
                 ['/items/' + str(i) for i in range(1024, -1, -1)],
                 ['/items/0', '/dup'], ['/items/0', '/missing'],
                 ['/items/0', '/items/00'], ['/items/0', '/a~2b'],
                 ['/items/0', '/items/-'], ['/items/0', '/items/' + '9' * 100]]
        for pointers in cases:
            with self.subTest(pointers=pointers[:5]):
                encoded = json.dumps(pointers, ensure_ascii=False).encode()
                pointer_path.write_bytes(encoded)
                try:
                    expected = '[' + ','.join(render(selected(value, p)) for p in pointers) + ']'
                    code, stdout = 0, (expected + '\n' + expected + '\n').encode()
                except (ValueError, KeyError) as error:
                    code = 2 if isinstance(error, ValueError) else 3
                    stdout = ','.join(pointers).encode()
                result = subprocess.run([exe, input_path, pointer_path], capture_output=True, timeout=60)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (code, stdout, b''))
                self.assertEqual(input_path.read_bytes(), data)
                self.assertEqual(pointer_path.read_bytes(), encoded)

if __name__ == '__main__':
    unittest.main()