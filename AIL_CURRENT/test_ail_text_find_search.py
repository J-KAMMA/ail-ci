"""Unicode character-index find over UTF-8 str storage, checked against Python strings."""
import _ctypes
import ctypes
import itertools
import os
import random
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support

class Text(ctypes.Structure):
    _fields_=[('p',ctypes.c_void_p),('n',ctypes.c_int64),('bytes',ctypes.c_bool)]

def canonical(points):
    return ''.join(map(chr,points))

HEADERS=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <string.h>
#ifdef _WIN32
#define API __declspec(dllexport)
#include <windows.h>
#else
#define API __attribute__((visibility("default")))
#include <sys/mman.h>
#include <unistd.h>
#endif
'''
WRAPPERS=r'''
API int64_t public_text_find(ail_str h,ail_str q){return ail_text_find_points(h,q);}
API uint64_t text_layout(int which){
 if(which==0)return sizeof(ail_str);if(which==1)return offsetof(ail_str,n);return offsetof(ail_str,bytes);
}
#ifndef SHARED_TEST
static int utf8_put(uint8_t *q,uint32_t c){
 if(c<0x80){q[0]=(uint8_t)c;return 1;}
 if(c<0x800){q[0]=(uint8_t)(0xC0|(c>>6));q[1]=(uint8_t)(0x80|(c&63));return 2;}
 if(c<0x10000){q[0]=(uint8_t)(0xE0|(c>>12));q[1]=(uint8_t)(0x80|((c>>6)&63));q[2]=(uint8_t)(0x80|(c&63));return 3;}
 q[0]=(uint8_t)(0xF0|(c>>18));q[1]=(uint8_t)(0x80|((c>>12)&63));q[2]=(uint8_t)(0x80|((c>>6)&63));q[3]=(uint8_t)(0x80|(c&63));return 4;
}
int main(int argc,char **argv){
 int mode=argc>1?atoi(argv[1]):0;uint8_t unit='a';ail_str h={&unit,1,1},q={&unit,1,1};
 if(mode){
  if(mode==1)h.n=-1;if(mode==2)h.p=NULL;if(mode==3)q.n=-1;if(mode==4)q.p=NULL;
  if(mode==5)h.n=INT64_MAX;
  ail_text_find_points(h,q);return 91;
 }
 /* Every scalar value: XOR 1 never changes the UTF-8 length (length boundaries are multiples of
    0x80) and never leaves or enters the surrogate gap, so the haystack is 32 other characters. */
 uint8_t sweep[32*4],target[4];
 for(uint32_t value=0;value<0x110000;value++){
  if(value>=0xD800&&value<=0xDFFF)continue;
  int w=utf8_put(target,value);
  for(int i=0;i<32;i++)utf8_put(sweep+i*w,value^1u);
  h=(ail_str){sweep,32*w,value<0x80};q=(ail_str){target,w,value<0x80};
  if(ail_text_find_points(h,q)!=-1)return 99;
  memcpy(sweep,target,(size_t)w);
  if(ail_text_find_points(h,q)!=0)return 100;
  utf8_put(sweep,value^1u);memcpy(sweep+31*w,target,(size_t)w);
  if(ail_text_find_points(h,q)!=31)return 101;
 }
 size_t page;unsigned char *mapping;
#ifdef _WIN32
 SYSTEM_INFO info;GetSystemInfo(&info);page=info.dwPageSize;
 mapping=VirtualAlloc(NULL,page*6,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!mapping)return 92;
 DWORD old;
 if(!VirtualProtect(mapping,page,PAGE_NOACCESS,&old)||!VirtualProtect(mapping+5*page,page,PAGE_NOACCESS,&old))return 93;
#else
 page=(size_t)sysconf(_SC_PAGESIZE);
 mapping=mmap(NULL,page*6,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mapping==MAP_FAILED)return 92;
 if(mprotect(mapping,page,PROT_NONE)||mprotect(mapping+5*page,page,PROT_NONE))return 93;
#endif
 int sizes[]={1,7,8,15,16,31,32,33,63,64,65,257,1025,4097};
 for(size_t k=0;k<sizeof sizes/sizeof *sizes;k++)for(int side=0;side<2;side++){
  int n=sizes[k];size_t span=(size_t)n;if(span>page*4)return 98;
  unsigned char *p=side?mapping+5*page-span:mapping+page;
  memset(p,'a',span);
  unsigned char narrow[33];
  for(int i=0;i<33;i++)narrow[i]='a';
  narrow[16]='b';
  h=(ail_str){p,n,1};
  q=(ail_str){narrow,33,1};
  if(ail_text_find_points(h,q)!=-1)return 94;
  if(n>=33){
   memcpy(p+n-33,narrow,33);
   if(ail_text_find_points(h,q)!=n-33)return 95;
   q=(ail_str){p+n-33,33,1};
   if(ail_text_find_points(h,q)!=n-33)return 96;
   memset(p,'a',span);
  }
 }
#ifdef _WIN32
 if(!VirtualFree(mapping,0,MEM_RELEASE))return 97;
#else
 if(munmap(mapping,page*6))return 97;
#endif
 return 0;
}
#endif
'''

class TextFindSearchTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write

    def test_unicode_latin1_surrogates_periodic_binary_and_guard_pages(self):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            import cruntime
            code=cruntime.emit({'STR'})
        finally:
            sys.path.pop(0)
        self.assertIn('ail_text_find_points(',code)
        compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        self.assertTrue(compiler,'C compiler required')
        path=self.write('text_find.c',HEADERS+code+WRAPPERS)
        library=self.root/('text_find.dll' if os.name=='nt' else 'text_find.so')
        result=subprocess.run([compiler,'-std=c11','-D_DEFAULT_SOURCE','-DSHARED_TEST','-shared','-fPIC','-O2',
                               str(path),'-lm','-o',str(library)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
        loaded=ctypes.CDLL(str(library))
        self.addCleanup(_ctypes.FreeLibrary if os.name=='nt' else _ctypes.dlclose,loaded._handle)
        loaded.text_layout.argtypes=[ctypes.c_int];loaded.text_layout.restype=ctypes.c_uint64
        self.assertEqual([loaded.text_layout(i) for i in range(3)],
                         [ctypes.sizeof(Text),Text.n.offset,Text.bytes.offset])
        fn=loaded.public_text_find;fn.argtypes=[Text,Text];fn.restype=ctypes.c_int64
        def check(h,q):
            data_h=canonical(h).encode('utf-8');data_q=canonical(q).encode('utf-8')
            hay=(ctypes.c_uint8*max(1,len(data_h))).from_buffer_copy(data_h or b'\0')
            needle=(ctypes.c_uint8*max(1,len(data_q))).from_buffer_copy(data_q or b'\0')
            before=(bytes(hay),bytes(needle))
            actual=fn(Text(ctypes.addressof(hay),len(data_h),data_h.isascii()),
                      Text(ctypes.addressof(needle),len(data_q),data_q.isascii()))
            self.assertEqual(actual,canonical(h).find(canonical(q)),(h[:20],q[:20]))
            self.assertEqual((bytes(hay),bytes(needle)),before)
        astral=0x1F600
        units=((),(0,),(255,),tuple(map(ord,'日本語')),(astral,),(astral,ord('a')),(ord('a'),0x301),
               (astral,astral,0),(0x65e5,astral,0x65e5),(0x7f,0x80,0x7ff,0x800,0xffff,0x10000,0x10ffff))
        for h in units:
            for q in units:check(h,q)
        needles=[word for m in range(2,6) for word in itertools.product((0,1),repeat=m)]
        for h in itertools.product((0,1),repeat=8):
            for q in needles:check(h,q)
        for m in (1,2,31,32,33,63,64,65,257,1025,4097):
            for q in ((97,)*m,(97,)*(m//2)+(98,)+(97,)*(m-m//2-1),((astral,0x65e5)*((m+1)//2))[:m]):
                for h in (q*2,(97,)*(m*2+1),(astral,0x65e5)+q):
                    check(h,q)
            check((255,)*m+(0,)+(255,)*m,(0,255))
        rng=random.Random(638)
        alphabet=(0,1,255,97,0xd7ff,0xe000,astral,0x301,0x65e5,0x10ffff)
        for _ in range(128):
            h=tuple(rng.choice(alphabet) for _ in range(rng.randrange(65)))
            q=tuple(rng.choice(alphabet) for _ in range(rng.randrange(34)))
            check(h,q)
        executable=self.root/('pages.exe' if os.name=='nt' else 'pages')
        result=subprocess.run([compiler,'-std=c11','-D_DEFAULT_SOURCE','-O2',str(path),'-lm','-o',str(executable)],
                              capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
        for mode in range(6):
            result=subprocess.run([str(executable),str(mode)],capture_output=True,timeout=60)
            diagnostic=b'allocation too large\n' if mode in (1,3,5) else b'invalid string text\n'
            expected=(0,b'',b'') if mode==0 else (1,b'',diagnostic)
            self.assertEqual((result.returncode,result.stdout,result.stderr.replace(b'\r\n',b'\n')),expected)

if __name__=='__main__':
    unittest.main()
