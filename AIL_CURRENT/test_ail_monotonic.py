"""Elapsed clock, rejection/shadowing, OS faults and integer boundaries."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

class MonotonicTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build

    def test_real_elapsed_source_free_and_frontends(self):
        provider='fn tick()->int { return monotonic_ms(); }'
        obj=self.ail_build('clock',provider,library=True)
        moved=self.root/'moved clock 😀';moved.mkdir();target=moved/obj.name
        shutil.move(obj,target);shutil.move(str(obj)+'.json',str(target)+'.json')
        source='fn main()->int { let start=tick();let listener=tcp_listen("127.0.0.1",0,1);listener.wait_readable(80);listener.close();let end=monotonic_ms();print(start,end,end-start);return 0; }'
        exe=self.ail_build('elapsed',source,target)
        begin=time.monotonic();result=subprocess.run([str(exe)],capture_output=True,timeout=10);duration=time.monotonic()-begin
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        start,end,elapsed=map(int,result.stdout.split())
        self.assertGreaterEqual(start,0);self.assertEqual(end-start,elapsed)
        self.assertGreaterEqual(elapsed,50);self.assertLessEqual(elapsed,duration*1000+50)
        python=self.ail_build('pythonclock','def main()->int:\n print(monotonic_ms())\n return 0\nmain()\n')
        self.assertEqual(subprocess.run([str(python)],capture_output=True,timeout=10).returncode,0)

    def test_reject_arguments_and_preserve_user_name(self):
        for i,statement in enumerate(('monotonic_ms(1)','monotonic_ms(x=1)','let x=monotonic_ms(1)','print(monotonic_ms(x=1))')):
            path=self.write(f'bad{i}.ail',f'fn main()->int {{ {statement};return 0; }}');output=self.root/f'bad{i}'
            result=self.command('compile',path,'-o',output)
            self.assertNotEqual(result.returncode,0);self.assertFalse(output.exists());self.assertFalse(Path(str(output)+'.exe').exists())
        exe=build(self,'shadow','fn monotonic_ms(x:int)->int {return x+1;} fn main()->int {print(monotonic_ms(6));return 0;}')
        result=subprocess.run([str(exe)],capture_output=True,timeout=10)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,('7'+os.linesep).encode(),b''))

    def test_injected_os_failure_timespec_width_and_maximum_result(self):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            generated=to_c('def probe()->int:\n try:\n  return monotonic_ms()\n except OSError:\n  return -1\n',name='probe',strict=True,library=True)
        finally:sys.path.pop(0)
        prefix=r'''
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
static uint64_t clock_value;
static ULONGLONG WINAPI fake_tick(void){return clock_value;}
#define GetTickCount64 fake_tick
#else
#include <time.h>
static time_t seconds;static long nanos;static int fail;
static int fake_clock(clockid_t id,struct timespec *out){(void)id;out->tv_sec=seconds;out->tv_nsec=nanos;return fail;}
#define clock_gettime fake_clock
#endif
'''
        host=r'''
int main(void){
#ifdef _WIN32
 clock_value=0;if(probe()!=0)return 1;
 clock_value=INT64_MAX;if(probe()!=INT64_MAX)return 2;
 clock_value=(uint64_t)INT64_MAX+1;if(probe()!=-1)return 3;
#else
 seconds=0;nanos=0;if(probe()!=0)return 1;
 seconds=INT64_MAX/1000;nanos=(INT64_MAX%1000)*1000000;if(probe()!=INT64_MAX)return 2;
 nanos+=1000000;if(probe()!=-1)return 3;
 seconds=-1;nanos=0;if(probe()!=-1)return 4;
 seconds=0;nanos=-1;if(probe()!=-1)return 5;
 nanos=1000000000;if(probe()!=-1)return 6;
 nanos=0;fail=1;if(probe()!=-1)return 7;
#endif
 return 0;
}
'''
        path=self.write('fault.c',prefix+generated+host);exe=self.root/('fault.exe' if os.name=='nt' else 'fault')
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        result=subprocess.run([cc,'-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:3000].decode(errors='replace'))
        result=subprocess.run([str(exe)],capture_output=True,timeout=10)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))

if __name__=='__main__':unittest.main()