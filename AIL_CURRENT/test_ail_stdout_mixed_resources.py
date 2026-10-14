"""Dirty-payload copies must be released on success and flush exceptions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_ail_exception_resources import ALLOCATOR, ROOT

class MixedStdoutResourceTests(unittest.TestCase):
    def test_repeated_dirty_output_and_failed_flush_release_snapshot(self):
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            source='def run(n:int)->int:\n total=0\n for i in range(n):\n  print("p",end="")\n  try:\n   write_stdout_bytes(b"x")\n   total+=1\n  except OSError:\n   total+=2\n return total\n'
            source+='\ndef probe(data:bytes)->int:\n try:\n  write_stdout_bytes(data)\n  return 0\n except ValueError:\n  return 1\n'
            generated=to_c(source,name='run',strict=True,library=True)
        finally:
            sys.path.pop(0)
        prefix=r'''
#include <stdio.h>
static int fail_flush;
static int intercept_flush(FILE *f){return fail_flush&&f==stdout?EOF:fflush(f);}
#define fflush intercept_flush
'''
        host=r'''
#undef fflush
int main(int argc,char **argv){
 int n=argc>1?atoi(argv[1]):1;fail_flush=argc>2;
 if(probe((ail_bytes){NULL,1})!=1 || probe((ail_bytes){NULL,-1})!=1 ||
    probe((ail_bytes){(const unsigned char *)(uintptr_t)UINTPTR_MAX,1})!=1 ||
    probe((ail_bytes){NULL,0})!=0)return 9;
 if(ail_stdout_kind || ail_stdout_dirty || ail_cleanup_top || live || live_bytes)return 10;
 long long result=run(n);
 fflush(stdout);
 fprintf(stderr,"{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"frames\":%d,\"peak\":%zu}\n",result,live,live_bytes,ail_cleanup_top!=NULL,peak_bytes);
 return live||live_bytes||ail_cleanup_top?5:0;
}
'''
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        with tempfile.TemporaryDirectory(prefix='ail-mixed-resource-') as temporary:
            root=Path(temporary);path=root/'output.c';exe=root/('output.exe' if os.name=='nt' else 'output')
            path.write_text(prefix+ALLOCATOR+generated+host,encoding='utf8')
            result=subprocess.run([cc,'-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)],capture_output=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
            peaks=[]
            for n in (1,17,10000):
                result=subprocess.run([str(exe),str(n)],capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout,b'px'*n)
                measured=json.loads(result.stderr)
                self.assertEqual((measured['result'],measured['live'],measured['bytes'],measured['frames']),(n,0,0,0))
                peaks.append(measured['peak'])
            self.assertLessEqual(peaks[2],peaks[1])
            failed=subprocess.run([str(exe),'17','fail'],capture_output=True,timeout=30)
            self.assertEqual(failed.returncode,0,failed.stderr)
            self.assertEqual(failed.stdout,b'p'*17)
            measured=json.loads(failed.stderr)
            self.assertEqual((measured['result'],measured['live'],measured['bytes'],measured['frames']),(34,0,0,0))

if __name__=='__main__':unittest.main()