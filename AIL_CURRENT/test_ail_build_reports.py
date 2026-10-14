"""Real native diagnostics, source mapping, whole-output agreement and output protection."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import ail_chatgpt
import test_ail_c_objects as support

class BuildReportTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    def report(self,*args):
        r=self.command(*args,'--json');self.assertEqual(r.stderr,b'');d=json.loads(r.stdout)
        self.assertEqual((d['schema'],d['exit_code'],d['runtime_verified']),('ail.build/1',r.returncode,False))
        return r.returncode,d
    def passed(self,*args):
        code,data=self.report(*args);self.assertEqual(code,0,data);return data
    def binary(self,data,args,expected):
        r=subprocess.run([data['output']['output'],*map(str,args)],capture_output=True,timeout=30)
        self.assertEqual((r.returncode,r.stderr),(0,b''));self.assertEqual(r.stdout.replace(b'\r\n',b'\n'),expected)
    def test_exact_c_origins_and_independent_whole_output(self):
        neighbor=self.write('neighbor.ail','const LABEL="日本😀";\nfn double(value:int)->int {return value*2;}')
        source=self.write('main 日本.ail','use neighbor;\nfn main()->int {for value in sys.argv[1:] {print(double(int(value)));}return 0;}')
        debug=self.root/'debug 😀';data=self.passed('compile',source,'-o',self.root/'candidate','--debug-dir',debug)
        values=[-4611686018427387904,-23,0,17,4611686018427387903]
        self.binary(data,values,''.join(str(v*2)+'\n' for v in values).encode());self.assertTrue(data['link_verified'])
        generated=data['native_build']['generated'];self.assertEqual(len(generated),1)
        actual=Path(generated[0]['debug_path']).read_bytes();self.assertEqual(hashlib.sha256(actual).hexdigest(),generated[0]['sha256'])
        row=next(r for r in generated[0]['functions'] if r['function']=='double');self.assertTrue(row['mapped'])
        loc=row['source_location'];self.assertEqual((loc['path'],loc['line'],loc['function'],loc['location_kind']),(str(neighbor),2,'double','function_declaration'))
        self.assertEqual(loc['source_sha256'],hashlib.sha256(neighbor.read_bytes()).hexdigest());self.assertEqual(data['dependency_sha256'][str(neighbor)],loc['source_sha256'])
        previous=sys.path[:]
        try:
            sys.path.insert(0,str(support.ROOT/'python/pkg-v12'));pyc=importlib.import_module('pyc');info={'_checked_arrays':True}
            baseline=pyc.to_c(ail_chatgpt._load_sources(source)[0],strict=True,info=info)
            baseline+=pyc._io_main_for(info) if info.get('io') or info.get('ret')==pyc.NORET else pyc._main_for(info)
        finally:sys.path[:]=previous
        self.assertEqual(hashlib.sha256(actual.decode().replace('\r\n','\n').encode()).hexdigest(),hashlib.sha256(baseline.encode()).hexdigest())
        self.assertEqual(json.loads((debug/'ail_build.json').read_bytes()),data)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in debug.iterdir()}
        status,failed=self.report('compile',source,'-o',self.root/'refused','--debug-dir',debug)
        self.assertEqual((status,failed['stage']),(2,'configuration'));self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in debug.iterdir()})
    def test_real_gcc_error_keeps_source_without_publishing_outputs(self):
        source=self.root/'broken 日本.c';source.write_bytes((support.ROOT/'language_examples/file_identity.c').read_bytes()+b'\n#error AIL_REAL_REPORT_ERROR\n')
        status,data=self.report('compile-c',source,'--interface',support.ROOT/'language_examples/file_identity.json','-o',self.root/'broken.o','--debug-dir',self.root/'debug')
        self.assertNotEqual(status,0);self.assertEqual(data['stage'],'compile');self.assertFalse(data['link_verified'])
        self.assertFalse((self.root/'broken.o').exists());self.assertFalse((self.root/'broken.o.json').exists())
        op=data['native_build']['operations'][-1];self.assertIn('AIL_REAL_REPORT_ERROR',op['stderr']['text']);self.assertFalse(op['stderr']['truncated'])
        loc=next(r for r in data['diagnostics'] if 'AIL_REAL_REPORT_ERROR' in r['message'])
        self.assertEqual(loc['severity'],'error');self.assertIsNone(loc['source_location']);self.assertIsNone(loc['function'])
        kept=Path(loc['debug_path']);self.assertTrue(kept.is_file());self.assertEqual(hashlib.sha256(kept.read_bytes()).hexdigest(),loc['generated_sha256'])
        self.assertFalse(Path(data['native_build']['generated'][0]['path']).exists())
    def test_object_separate_link_and_library_reports(self):
        module=self.write('arithmetic.ail','fn bump(value:int)->int {return value+2;}');source=self.write('entry.ail','fn main()->int {print(bump(3));return 0;}')
        obj=self.passed('compile-module',module,'-o',self.root/'arithmetic.o');self.assertFalse(obj['link_verified']);self.assertEqual(obj['native_build']['operations'][-1]['phase'],'compile')
        linked=self.passed('compile',source,'--object',obj['output']['output'],'-o',self.root/'linked');self.binary(linked,[],b'5\n')
        separate=self.write('separate.ail','use arithmetic; fn main()->int {print(bump(3));return 0;}')
        split=self.passed('compile',separate,'--separate','-o',self.root/'split');self.assertEqual([r['phase'] for r in split['native_build']['operations']],['compile','compile','link']);self.binary(split,[],b'5\n')
        library=self.passed('compile-library',module,'--name','report_math','-o',self.root/'library');self.assertFalse(library['link_verified'])
        self.assertEqual(library['native_build']['operations'][-1]['phase'],'compile');self.assertTrue((self.root/'library/report_math.h').is_file());self.assertTrue((self.root/'library/report_math.o').is_file())
    def test_type_and_configuration_failures_preserve_outputs(self):
        source=self.write('bad.ail','fn main()->int {return "wrong";}');status,data=self.report('compile',source,'-o',self.root/'bad')
        self.assertEqual((status,data['stage']),(3,'type'));self.assertFalse((self.root/'bad').exists());self.assertFalse((self.root/'bad.exe').exists())
        kept=self.write('existing','keep');status,data=self.report('compile',source,'-o',kept)
        self.assertEqual((status,data['stage']),(2,'configuration'));self.assertEqual(kept.read_bytes(),b'keep')
if __name__=='__main__':unittest.main()