from test_ail_csv_reference import write_rows, read_rows
"""Fixed-profile CSV rewrite: full Python oracle and tracked native resources."""
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support
from test_ail_exception_resources import ALLOCATOR


FILE_TRACKER = r'''
#ifdef _WIN32
#include <wchar.h>
#endif
static int opened_files, closed_files;
static FILE *tracked_fopen(const char *path,const char *mode){
 FILE *f=fopen(path,mode); if(f)++opened_files;return f;
}
#ifdef _WIN32
static FILE *tracked_wfopen(const wchar_t *path,const wchar_t *mode){
 FILE *f=_wfopen(path,mode);if(f)++opened_files;return f;
}
#define _wfopen tracked_wfopen
#endif
static int tracked_fclose(FILE *f){int result=fclose(f);++closed_files;return result;}
#define fopen tracked_fopen
#define fclose tracked_fclose
'''


def encode(rows):
    out = io.StringIO(newline='')
    out.write(write_rows(rows))
    return out.getvalue().encode('utf-8')


def parse(data):
    return list(read_rows(data.decode('utf-8')))


class CsvRewriteResourceTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write

    def native(self):
        from ail_chatgpt import _load_sources
        input_path, output_path = self.root / 'input.csv', self.root / 'output.csv'
        entry = self.write('entry.ail', '''use csv_rewrite_stream;
fn open_writer(path:str,readonly:int)->binaryfile {
    if readonly==1 { return open_binary(path,"r"); }
    return open_binary(path,"w");
}
fn run(cap:int, readonly:int, chunk:int)->int {
    let reader=open_binary(INPUT,"r");
    let writer=open_writer(OUTPUT,readonly);
    let result:int=0;
    try {
        try { result=csv_rewrite_stream(reader,writer,chunk,cap); }
        except ValueError { result=-2; }
        except UnicodeDecodeError { result=-3; }
        except OSError { result=-4; }
        if reader.closed or writer.closed { result=999; }
    } finally { reader.close(); writer.close(); }
    return result;
}
'''.replace('INPUT', json.dumps(str(input_path))).replace('OUTPUT', json.dumps(str(output_path))))
        source = _load_sources(entry, module_only=True,
                               module_paths=(support.ROOT / 'language_examples',))[0]
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            generated = to_c(source, name='run', strict=True, library=True)
        finally:
            sys.path.pop(0)
        drain = ('for(int64_t j=0;j<ail__blk_cache_n;j++)count_free(ail__blk_cache[j].p);'
                 'ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in generated else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        host = r'''int main(int argc,char **argv){
 if(argc!=4)return 8; long long result=run(atoi(argv[1]),atoi(argv[2]),atoi(argv[3]));DRAIN
 printf("{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"frames\":%d,\"opened\":%d,\"closed\":%d}\n",
 result,live,live_bytes,peak_bytes,ail_cleanup_top!=NULL,opened_files,closed_files);
 return live||live_bytes||ail_cleanup_top||opened_files!=closed_files?5:0;
}'''.replace('DRAIN', drain)
        path = self.write('resource.c', ALLOCATOR + FILE_TRACKER + generated + host)
        exe = self.root / ('resource.exe' if os.name == 'nt' else 'resource')
        cc = os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        self.assertTrue(cc, 'C compiler is required')
        flags = ['-std=c11', *FLAGS, str(path), '-lm', '-o', str(exe)]
        if os.name != 'nt':
            flags.insert(0, '-D_POSIX_C_SOURCE=200809L')
        built = subprocess.run([cc, *flags], capture_output=True, timeout=180)
        self.assertEqual(built.returncode, 0, built.stderr[:2500].decode(errors='replace'))
        return exe, input_path, output_path

    def invoke(self, exe, cap=4096, readonly=0, chunk=257):
        result = subprocess.run([str(exe), str(cap), str(readonly), str(chunk)], capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[:2000].decode(errors='replace'))
        self.assertEqual(result.stderr, b'')
        measured = json.loads(result.stdout)
        self.assertEqual((measured['live'], measured['bytes'], measured['frames']), (0, 0, 0))
        self.assertEqual((measured['opened'], measured['closed']), (2, 2))
        return measured

    def test_complete_long_stream_and_failure_cleanup(self):
        exe, input_path, output_path = self.native()
        template = [['plain', '日本語😀', '\0'], ['a,b', 'quote"', 'line\r\nnext'],
                    ['', '', 'x' * 301], ['single'], ['']]
        peaks = []
        for count in (16, 512, 4096):
            rows = [template[i % len(template)] for i in range(count)]
            data = encode(rows)
            input_path.write_bytes(data)
            before = hashlib.sha256(input_path.read_bytes()).hexdigest()
            measured = self.invoke(exe)
            self.assertEqual(measured['result'], count)
            actual = output_path.read_bytes()
            expected = encode(parse(data))
            self.assertEqual(len(actual), len(expected))
            self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(expected).digest())
            self.assertEqual(parse(actual), rows)
            self.assertEqual(hashlib.sha256(input_path.read_bytes()).hexdigest(), before)
            peaks.append(measured['peak'])
        print(f'tracked CSV peaks 16/512/4096 rows: {peaks}', flush=True)
        # Fixed row shapes/chunk/cap: allow one 8KiB allocator-cache size-class step,
        # not growth proportional to the 3584 additional rows. Requested heap, not RSS.
        self.assertLessEqual(peaks[2], peaks[1] + 8192, f'late requested-heap growth: {peaks}')
        for suffix, expected in ((b'"unfinished', -2), (b'"closed"suffix', -2), (b'\xff', -2)):
            data = encode(template * 100) + suffix
            input_path.write_bytes(data)
            measured = self.invoke(exe)
            self.assertEqual(measured['result'], expected)
            self.assertEqual(input_path.read_bytes(), data)
            emitted = parse(output_path.read_bytes())
            self.assertTrue(emitted)
            self.assertEqual(emitted, (template * 100)[:len(emitted)])
        input_path.write_bytes(encode([['x' * 65]]))
        self.assertEqual(self.invoke(exe, cap=64)['result'], -2)
        input_path.write_bytes(b'a' * 1048576)
        early = self.invoke(exe, cap=1, chunk=1048576)
        self.assertEqual(early['result'], -2)
        self.assertEqual(output_path.read_bytes(), b'')
        self.assertLess(early['peak'], 16 * 1048576, 'quota must precede quadratic field assembly')
        print(f'oversized-row early-rejection peak: {early["peak"]}', flush=True)
        input_path.write_bytes(encode(template))
        output_path.write_bytes(b'keep')
        self.assertEqual(self.invoke(exe, readonly=1)['result'], -4)
        self.assertEqual(output_path.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()