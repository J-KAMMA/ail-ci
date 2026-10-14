"""Config CLI checked against an independent standard Python reference."""
import json
import os
import re
import shutil
import subprocess
import unittest
import test_ail_c_objects as support

LOW, HIGH = -(1 << 63), (1 << 63) - 1

def reference(payload=None, *, missing=False, usage=False):
    if usage: return 2, '', 'usage: config_validate INPUT\n'
    if missing: return 3, '', 'OSError: file error\n'
    try: text = payload.decode('utf8')
    except UnicodeDecodeError: return 4, '', 'UnicodeDecodeError: input must be UTF-8\n'
    count = total = 0
    try:
        for number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('#'): continue
            prefix = f'line {number}: '
            parts = line.split('=')
            if len(parts) != 2: raise ValueError(prefix + 'expected key=integer')
            key, token = map(str.strip, parts)
            if not key: raise ValueError(prefix + 'empty key')
            if not re.fullmatch(r'[+-]?[0-9]+', token):
                raise ValueError(prefix + 'invalid integer: ' + token)
            # Strip zeroes before int to avoid Python's decimal conversion limit.
            digits = token.lstrip('+-').lstrip('0') or '0'
            if len(digits) > 19: raise ValueError(prefix + 'invalid integer: ' + token)
            value = int(('-' if token.startswith('-') else '') + digits)
            if not LOW <= value <= HIGH: raise ValueError(prefix + 'invalid integer: ' + token)
            total += value
            if not LOW <= total <= HIGH: raise ValueError(prefix + 'total outside int64')
            count += 1
    except ValueError as error: return 2, '', f'ValueError: {error}\n'
    return 0, f'{{"count":{count},"total":{total}}}\n', ''

class ConfigReferenceTests(unittest.TestCase):
    def test_known_results(self):
        for payload, expected in [
            ('日本=+2\n# comment\n二=-3\n'.encode(), (0, '{"count":2,"total":-1}\n', '')),
            (b'x=9223372036854775808', (2, '', 'ValueError: line 1: invalid integer: 9223372036854775808\n')),
            (b'x=9223372036854775807\ny=1', (2, '', 'ValueError: line 2: total outside int64\n')),
            (b'x=' + b'0' * 5000 + b'1', (0, '{"count":1,"total":1}\n', ''))]:
            self.assertEqual(reference(payload), expected)

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class ExceptionValuesAppTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build

    def assert_process(self, executable, expected, *args):
        result = subprocess.run([str(executable), *map(str, args)], capture_output=True, timeout=30)
        def encode(text):
            return text.replace('\n', '\r\n').encode() if os.name == 'nt' else text.encode()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (expected[0], encode(expected[1]), encode(expected[2])))

    def test_config_cli_reference_and_file_cleanup(self):
        examples = support.ROOT / 'language_examples'
        shutil.copy2(examples / 'checked_integer.ail', self.root / 'checked_integer.ail')
        shutil.copy2(examples / 'config_core.ail', self.root / 'config_core.ail')
        executable = self.ail_build('config_validate',
                                   (examples / 'config_validate.ail').read_text(encoding='utf-8-sig'))
        path = self.root / '設定😀.txt'
        cases = ['', '# only\n\n', '日本=+2\n二=-3\r\n', 'x=1\nx=2',
                 f'x={LOW}', f'x={HIGH}', f'x={HIGH}\ny=1', f'x={LOW}\ny=-1',
                 f'x={HIGH+1}', f'x={LOW-1}', 'x=+', 'x=1_0', 'x=１２',
                 'x=1\n\nwrong', '=2', 'x=1=2', 'x=', 'x=日本😀',
                 'x=' + '日😀' * 8193, 'x=' + '0' * 5000 + '1']
        for payload in [*(text.encode() for text in cases), b'\xff']:
            with self.subTest(bytes=len(payload), prefix=payload[:40]):
                path.write_bytes(payload)
                self.assert_process(executable, reference(payload), path)
                self.assertEqual(path.read_bytes(), payload)
                # On Windows an unclosed file handle prevents rename/delete.
                moved = path.with_suffix('.moved')
                path.rename(moved)
                moved.unlink()
        self.assert_process(executable, reference(missing=True), path)
        self.assert_process(executable, reference(usage=True))
        self.assert_process(executable, reference(usage=True), path, 'extra')

    def test_batch_retains_errors_and_struct_fields_until_reporting(self):
        examples = support.ROOT / 'language_examples'
        for name in ('checked_integer.ail', 'config_core.ail', 'json_text.ail'):
            shutil.copy2(examples / name, self.root / name)
        binary = self.ail_build('config_batch', (examples / 'config_batch.ail').read_text(encoding='utf8'))
        paths = []; expected = {'reports': [], 'errors': []}
        payloads = [b'x=2\ny=-3', b'x=bad', b'x=9223372036854775807\ny=1', b'\xff',
                    ('x=' + '日😀' * 8193).encode(), b'x=-9223372036854775808', None]
        for i, payload in enumerate(payloads):
            path = self.root / ('設定%d😀.txt' % i); paths.append(path)
            if payload is not None: path.write_bytes(payload)
            status, output, error = reference(payload, missing=payload is None)
            if not status:
                expected['reports'].append({'path': str(path), 'summary': json.loads(output)})
            else:
                kind, _, message = error.rstrip('\n').partition(': ')
                expected['errors'].append({'path': str(path), 'kind': kind, 'message': message})
        result = subprocess.run([str(binary), *map(str, paths)], capture_output=True, timeout=30)
        wanted = (json.dumps(expected, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(result.stdout, wanted)
        good_paths = [paths[0], paths[5]]
        good_expected = {'reports': [expected['reports'][0], expected['reports'][1]], 'errors': []}
        result = subprocess.run([str(binary), *map(str, good_paths)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stderr), (0, b''))
        self.assertEqual(result.stdout, (json.dumps(good_expected, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
        self.assert_process(binary, (2, '', 'usage: config_batch INPUT...\n'))
        for path, payload in zip(paths, payloads):
            if payload is not None:
                self.assertEqual(path.read_bytes(), payload)
                path.unlink()

    def test_batch_merge_owns_string_fields_and_preserves_source(self):
        examples = support.ROOT / 'language_examples'
        for name in ('checked_integer.ail', 'config_core.ail', 'json_text.ail'):
            shutil.copy2(examples / name, self.root / name)
        prefix = (examples / 'config_batch.ail').read_text(encoding='utf8').split('fn main()', 1)[0]
        main = '''fn main()->int {
            let left=validate_many(sys.argv[1:2]);let right=validate_many(sys.argv[2:]);
            let saved=batch_json(right);let merged=merge_config_batches(left,right);
            if batch_json(right)!=saved {return 9;}
            write_stdout_bytes((batch_json(merged)+"\\n").encode());return 0;
        }'''
        binary = self.ail_build('config_merge', prefix + main)
        payloads = [b'x=2\ny=-3', 'x=日本😀'.encode(), b'y=4']
        paths=[]; wanted={'reports': [], 'errors': []}
        for i, payload in enumerate(payloads):
            path=self.root/('merge%d.txt' % i);path.write_bytes(payload);paths.append(path)
            status, output, error=reference(payload)
            if status:
                kind, _, message=error.rstrip('\n').partition(': ')
                wanted['errors'].append({'path': str(path), 'kind': kind, 'message': message})
            else:
                wanted['reports'].append({'path': str(path), 'summary': json.loads(output)})
        result=subprocess.run([str(binary), *map(str,paths)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        self.assertEqual(result.stdout,(json.dumps(wanted,ensure_ascii=False,separators=(',',':'))+'\n').encode())

    def test_empty_unicode_long_messages_rethrow_and_finally(self):
        for index, message in enumerate(('', '日本😀', '日😀' * 8193)):
            source = '''fn main() -> int {
                let finalized: int = 0;
                try {
                    try {
                        try { raise ValueError(MESSAGE); }
                        except ValueError as e { raise e; }
                    } except ValueError { raise; }
                    finally { finalized += 1; }
                } except ValueError as e {
                    print(e.kind); print(e.message); print(finalized);
                    return 0;
                }
                return 9;
            }'''.replace('MESSAGE', '"' + message + '"')
            executable = self.ail_build('messages_' + str(index), source)
            self.assert_process(executable, (0, 'ValueError\n' + message + '\n1\n', ''))

if __name__ == '__main__': unittest.main()
