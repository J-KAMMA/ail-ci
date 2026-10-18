"""Ordered mixed output, exact binary bytes and mode sharing across objects."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build
from ail_testenv import glibc_cookie_streams

SOURCE=r'''fn main()->int {
 let payload=read_bytes(sys.argv[1]);print("header");
 write_stdout_bytes(payload);print("tail",end="");
 write_stdout_bytes(b"\r\n\x1a\0\xff");print(7);
 write_stdout_bytes(b"");print("日本語😀");return 0;
}'''
class MixedStdoutTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    c_object=support.CObjectTests.c_object
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def test_text_binary_alternation_preserves_order_all_bytes_and_line_endings(self):
        exe=build(self,'mixed',SOURCE);path=self.root/'payload.bin';newline=os.linesep.encode()
        for data in (b'',b'\0\r\n\x1a\xff',bytes(range(256))*257):
            path.write_bytes(data)
            result=subprocess.run([str(exe),str(path)],capture_output=True,timeout=15)
            expected=b'header'+newline+data+b'tail\r\n\x1a\0\xff7'+newline+'日本語😀'.encode()+newline
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))
            self.assertEqual(path.read_bytes(),data)

    def test_linked_text_and_binary_functions_share_mode_and_order(self):
        provider='fn text(value:str)->void { print(value); }\nfn raw(value:bytes)->void { write_stdout_bytes(value); }'
        obj=self.ail_build('provider',provider,library=True)
        moved=self.root/'moved mixed output 😀';moved.mkdir();target=moved/obj.name
        shutil.move(obj,target);shutil.move(str(obj)+'.json',str(target)+'.json');before=self.snapshot(target)
        source='fn main()->int { text("first");raw(b"\\0\\xff");text("second");raw(b"\\r\\n");print("last");return 0; }'
        exe=self.ail_build('entry',source,target)
        result=subprocess.run([str(exe)],capture_output=True,timeout=15);newline=os.linesep.encode()
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'first'+newline+b'\0\xffsecond'+newline+b'\r\nlast'+newline,b''))
        self.assertEqual(self.snapshot(target),before)

    def test_closed_stdout_flush_or_mode_failure_is_catchable(self):
        native='#ifdef _WIN32\n#include <io.h>\n#else\n#include <unistd.h>\n#endif\nvoid close_output(void) {\n#ifdef _WIN32\n_close(1);\n#else\nclose(1);\n#endif\n}'
        obj=self.c_object(native,dict(version=1,functions={'close_output':support.signature('close_output',[],'void')}))
        cases=(('pending','fn main()->int { print("pending");close_output();try { write_stdout_bytes(b"X");return 9; }except OSError { return 6; }}',b''),
               ('after','fn main()->int { write_stdout_bytes(b"A");close_output();try { print("B");flush_stdout();return 9; }except OSError {return 6;}}',b'A'))
        for name,source,expected in cases:
            exe=self.ail_build(name,source,obj)
            result=subprocess.run([str(exe)],capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(6,expected,b''))

    @unittest.skipUnless(os.name=='nt','Windows initial descriptor mode')
    def test_original_binary_descriptor_mode_is_restored_for_text(self):
        native='#include <io.h>\n#include <fcntl.h>\nvoid initial_binary(void) { _setmode(1,_O_BINARY); }'
        obj=self.c_object(native,dict(version=1,functions={'initial_binary':support.signature('initial_binary',[],'void')}))
        exe=self.ail_build('initial','fn main()->int { initial_binary();print("first");write_stdout_bytes(b"raw\\r\\n");print("last");return 0; }',obj)
        result=subprocess.run([str(exe)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'first\nraw\r\nlast\n',b''))

    @unittest.skipUnless(os.name=='nt','Windows descriptor mode')
    def test_native_mode_change_does_not_translate_following_binary(self):
        native='#include <io.h>\n#include <fcntl.h>\nvoid native_text(void) { _setmode(1,_O_TEXT); }'
        obj=self.c_object(native,dict(version=1,functions={'native_text':support.signature('native_text',[],'void')}))
        exe=self.ail_build('flip','fn main()->int { write_stdout_bytes(b"A");native_text();write_stdout_bytes(b"B\\n\\0\\xff");print("last");return 0; }',obj)
        result=subprocess.run([str(exe)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'AB\n\0\xfflast\r\n',b''))

    @unittest.skipUnless(glibc_cookie_streams(),'glibc stdout callback: fopencookie exists only in glibc (macOS has funopen, MinGW neither)')
    def test_flush_callback_cannot_corrupt_live_input_and_borrowed_echo(self):
        native=r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifndef __USE_GNU
typedef struct {ssize_t (*read)(void *,char *,size_t);ssize_t (*write)(void *,const char *,size_t);int (*seek)(void *,int64_t *,int);int (*close)(void *);} cookie_io_functions_t;
extern FILE *fopencookie(void *,const char *,cookie_io_functions_t);
#endif
extern unsigned char ail_stdin_buf[];
static ssize_t callback(void *context,const char *p,size_t n){(void)context;memset(ail_stdin_buf,'a',65536);return write(1,p,n);}
int64_t install_callback(void){cookie_io_functions_t io={0};io.write=callback;FILE *stream=fopencookie(NULL,"w",io);if(!stream)return -1;stdout=stream;return 0;}
'''
        obj=self.c_object(native,dict(version=1,functions={'install_callback':support.signature('install_callback',[])}))
        owned='fn main()->int { install_callback();while true { let data=read_stdin_bytes(2);if len(data)==0 {break;}print("tick");write_stdout_bytes(data); }return 0; }'
        borrowed='fn main()->int { install_callback();print("head");while true {let data=read_stdin_bytes(2);if len(data)==0 {break;}write_stdout_bytes(data);}return 0;}'
        for name,source,expected in (('owned',owned,b'tick\nxy'),('borrowed',borrowed,b'head\nxy')):
            exe=self.ail_build(name,source,obj)
            result=subprocess.run([str(exe)],input=b'xy',capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))

    @unittest.skipUnless(glibc_cookie_streams(),'glibc mutable-buffer callback: fopencookie exists only in glibc (macOS has funopen, MinGW neither)')
    def test_dirty_flush_snapshots_mutable_payload_before_callback_reallocation(self):
        import sys
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            code=to_c('def run(data:bytearray)->int:\n print("header")\n write_stdout_bytes(data)\n write_stdout_bytes(data)\n return 0\n',name='run',strict=True,library=True)
        finally:
            sys.path.pop(0)
        host=r'''
static ail_bytearray *held;
static ssize_t mutate(void *context,const char *p,size_t n){
 (void)context;
 if(held){unsigned char *fresh=malloc((size_t)held->n+65536);if(!fresh)abort();
 memset(fresh,'Z',(size_t)held->n);free(held->p);held->p=fresh;held->cap=held->n+65536;held=NULL;}
 return write(1,p,n);
}
int main(void){
 ail_bytearray *data=ail_bytearray_from_bytes((ail_bytes){(const unsigned char *)"payload",7});
 cookie_io_functions_t io={0};io.write=mutate;FILE *stream=fopencookie(NULL,"w",io);
 if(!stream)return 8;FILE *previous=stdout;held=data;stdout=stream;
 int result=run(data);stdout=previous;fclose(stream);ail_bytearray_release(data);return result;
}
'''
        path=self.write('mutable.c','#define _GNU_SOURCE\n'+code+host)
        exe=self.root/'mutable'
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        result=subprocess.run([cc,'-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
        result=subprocess.run([str(exe)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'header\npayloadZZZZZZZ',b''))
    def test_mutable_buffer_field_return_and_list_inputs(self):
        source=r'''struct Chunk { data:bytearray; }
fn make()->bytearray { return bytearray(b"return"); }
fn main()->int {
 let value=bytearray(b"direct\0\xff");print("header");write_stdout_bytes(value);
 let holder=Chunk(bytearray(b"field"));write_stdout_bytes(holder.data);
 write_stdout_bytes(make());let values:list[bytearray]=[bytearray(b"list")];write_stdout_bytes(values[0]);
 print("end");return 0;
}'''
        exe=build(self,'buffers',source)
        result=subprocess.run([str(exe)],capture_output=True,timeout=15)
        newline=os.linesep.encode()
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'header'+newline+b'direct\0\xfffieldreturnlistend'+newline,b''))

if __name__=='__main__':unittest.main()