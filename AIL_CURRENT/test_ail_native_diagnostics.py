"""Native diagnostic helper boundaries without executing a native compiler."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class NativeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='ail-native-report-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        path=Path(__file__).resolve().parent/'python/pkg-v12/native_diagnostics.py'
        spec=importlib.util.spec_from_file_location('native_report_test',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)

    def test_default_is_exact_subprocess_passthrough_and_no_generated_read(self):
        result=subprocess.CompletedProcess(['cc'],0,b'ok',b'')
        with patch.object(self.module.subprocess,'run',return_value=result) as command:
            self.assertIs(self.module.run(['cc'],phase='compile',cwd=self.root,capture_output=True),result)
            command.assert_called_once_with(['cc'],cwd=self.root,capture_output=True)
        self.assertIsNone(self.module.generated(self.root/'missing.c',[('f','body')]))
        self.module.failure(ValueError('unconfigured'))
        self.assertFalse(self.module.enabled())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_windows_unicode_locations_warnings_notes_and_linker_unknown(self):
        report=self.root/'report.json';self.module.configure(report)
        text='C:\\日本 dir\\file.c:12:7: error: broken\nC:\\日本 dir\\file.c:3: warning: odd\n/tmp/a.c:4:2: note: here\nld: undefined reference to missing\n'
        result=subprocess.CompletedProcess(['cc'],1,'',text)
        with patch.object(self.module.subprocess,'run',return_value=result):
            self.assertIs(self.module.run(['cc'],phase='link',text=True,capture_output=True),result)
        operation=json.loads(report.read_text(encoding='utf8'))['operations'][0]
        self.assertEqual(operation['exit_code'],1)
        self.assertEqual([(row['path'],row['line'],row['column'],row['severity']) for row in operation['locations']],
                         [('C:\\日本 dir\\file.c',12,7,'error'),('C:\\日本 dir\\file.c',3,None,'warning'),('/tmp/a.c',4,2,'note')])
        self.assertIn('undefined reference',operation['stderr']['text'])
        self.assertEqual(len(operation['locations']),3)

    def test_stream_caps_are_byte_based_and_explicit(self):
        self.module.configure(self.root/'report.json')
        self.assertTrue(self.module.enabled())
        result=subprocess.CompletedProcess(['cc'],0,b'x'*(self.module.LIMIT+1),'😀'*(self.module.LIMIT//4+1))
        with patch.object(self.module.subprocess,'run',return_value=result):self.module.run(['cc'],phase='compile')
        operation=self.module._report['operations'][0]
        for key in ('stdout','stderr'):
            self.assertTrue(operation[key]['truncated']);self.assertGreater(operation[key]['bytes'],self.module.LIMIT)
            self.assertLessEqual(len(operation[key]['text'].encode('utf8')),self.module.LIMIT)
        invalid=self.module._capture(b'\xff'*self.module.LIMIT)
        self.assertTrue(invalid['truncated'])
        self.assertLessEqual(len(invalid['text'].encode('utf8')),self.module.LIMIT)

    def test_generated_exact_unique_regions_sha_and_debug_no_overwrite(self):
        debug=self.root/'debug'
        self.module.configure(self.root/'report.json',debug)
        (debug/'unit.c').write_bytes(b'previous')
        source=self.root/'unit.c';body='int f(void) {\n return 1;\n}'
        source.write_text('// 日本\n'+body+'\n',encoding='utf8')
        item=self.module.generated(source,[('f',body),('missing','not present')])
        self.assertEqual((item['functions'][0]['c_line_start'],item['functions'][0]['c_line_end']),(2,4))
        self.assertEqual(item['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertFalse(item['functions'][1]['mapped'])
        self.assertEqual((debug/'unit.c').read_bytes(),b'previous')
        self.assertEqual(Path(item['debug_path']).read_bytes(),source.read_bytes())
        source.write_text(body+'\n'+body,encoding='utf8')
        self.assertFalse(self.module.generated(source,[('f',body)])['functions'][0]['mapped'])

    def test_debug_directory_is_new_and_failure_metadata_is_json_safe(self):
        existing=self.root/'existing';existing.mkdir()
        with self.assertRaises(FileExistsError):self.module.configure(self.root/'bad.json',existing)
        self.assertFalse((self.root/'bad.json').exists())
        report=self.root/'report.json';debug=self.root/'new'
        self.module.configure(report,debug)
        error=ValueError('bad source')
        error.source_position=('日本.ail',2,3)
        error.type_details={'expected':'int','actual':'str'}
        error.argument_details=object()
        self.module.failure(error)
        value=json.loads(report.read_text(encoding='utf8'))['failure']
        self.assertEqual(value['source_location'],['日本.ail',2,3])
        self.assertEqual(value['type_details'],error.type_details)
        self.assertNotIn('argument_details',value)
        self.assertEqual(json.loads((debug/'native_report.json').read_text(encoding='utf8'))['failure'],value)

    def test_oserror_recorded_and_same_exception_rethrown(self):
        report=self.root/'report.json';self.module.configure(report)
        error=FileNotFoundError(2,'missing compiler')
        with patch.object(self.module.subprocess,'run',side_effect=error),self.assertRaises(FileNotFoundError) as caught:
            self.module.run(['missing'],phase='compile')
        self.assertIs(caught.exception,error)
        operation=json.loads(report.read_text(encoding='utf8'))['operations'][0]
        self.assertIsNone(operation['exit_code']);self.assertEqual(operation['error']['errno'],2)
        with self.assertRaises(FileExistsError):self.module.configure(report)


if __name__=='__main__':unittest.main()