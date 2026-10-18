"""Bridge refusal boundaries and actual native allocations, streams and reentry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import zlib

import test_ail_c_objects as support
from ail_testenv import objcopy_available
OBJCOPY_REASON='symbol localization needs an ELF/COFF objcopy; Apple toolchains have none'

sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
import c_api_bridge as bridge
import cruntime
import module_object
from pyfront import Unsupported


class OwningBoundaryCodeTests(unittest.TestCase):
    def test_owning_boundary_rewrite_preserves_handlers_and_rejects_changed_markers(self):
        source=cruntime.emit(['DIE'])
        rewritten=bridge.rewrite_uncaught(source,'capture_trap')
        self.assertIn('capture_trap(value->code, message);',rewritten)
        self.assertIn('capture_trap(value->code, ail_exception_name(value->code));',rewritten)
        self.assertEqual(source[source.index('static void ail_raise_value'):],rewritten[rewritten.index('static void ail_raise_value'):])
        for bad in (source.replace('fputc(10, stderr); _Exit(1);','fputc(10, stderr); _Exit (1);'),source+source,source.replace('static void ail_exception_uncaught','static void changed_uncaught')):
            with self.subTest(changed=len(bad)),self.assertRaises(Unsupported):bridge.rewrite_uncaught(bad,'capture_trap')
        with self.assertRaises(Unsupported):bridge.rewrite_uncaught(source,'invalid();trap')

    def test_message_conversion_source_bounds_unicode_and_first_nul(self):
        source=bridge.rewrite_uncaught(cruntime.emit(['DIE']),'capture_trap')
        body=source[source.index('static void ail_exception_uncaught'):source.index('static void ail_raise_value')]
        # The message is UTF-8: whole characters are copied while they fit, stopping at the first NUL.
        self.assertIn('char message[160]',body)
        self.assertIn('i < value->n && raw[i]',body)
        self.assertIn('width > sizeof message - 1 - used || (int64_t)width > value->n - i',body)
        self.assertIn('message[used] = 0;',body)
        self.assertNotIn('strlen(',body)
        self.assertNotIn('malloc(',body)
        self.assertNotIn('_Exit(',body)
class BridgeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    snapshot=support.CObjectTests.snapshot

    def test_namespace_source_and_fatal_marker_boundaries(self):
        for name in ('', 'ail_private', 'x'*49, 'a-b', '日本', True, None):
            with self.assertRaises(Unsupported):bridge.validate_namespace(name)
        for name in ('a','x'*48):self.assertEqual(bridge.validate_namespace(name),name)
        for source in ('def f()->int:\n return input()\n','def f()->int:\n return len(sys.argv)\n'):
            with self.assertRaises(Unsupported):bridge.validate_source(source)
        source=cruntime.emit(['DIE'])
        rewritten=bridge.object_prefix(source,'demo')
        self.assertIn('demo_ail_bridge_trap(value->code, ail_exception_name(value->code));',rewritten)
        self.assertIn('#define ail_exc_top demo_ail_state_ail_exc_top',rewritten)
        with self.assertRaises(Unsupported):bridge.object_prefix(source.replace('_Exit(1);','_Exit (1);'),'demo')
        with self.assertRaises(Unsupported):bridge.object_prefix(source+'\nvoid f(void){_exit(1);}\n','demo')
        self.assertEqual(bridge.state_prefix('AIL_LINK_STATE(int, x[2], = 0);\nAIL_LINK_STATE(int, x[2], = 0);','demo'),
                         '#define x demo_ail_state_x\n')

    @unittest.skipUnless(objcopy_available(),OBJCOPY_REASON)
    def test_native_multiple_units_resource_cleanup_and_reentrant_guard(self):
        source=self.write('packet.c',r'''
#include <string.h>
extern void *allocate_piece(size_t size);
extern int host_reenter(void);
ail_c_bytes_view native_packet(const unsigned char *data, size_t size) {
    unsigned char *result=allocate_piece(size+1);
    FILE *stream=fopen("payload.dat","rb");
    if (!stream || host_reenter()!=10) return (ail_c_bytes_view){NULL,1};
    if (size==3) return (ail_c_bytes_view){NULL,1};
    for(size_t i=0;i<size;i++) result[i]=data[i]^255;
    fclose(stream);
    return (ail_c_bytes_view){result,size};
}
''')
        self.write('allocation.c','void *allocate_piece(size_t size) { return malloc(size); }\n')
        interface=self.write('packet.json',json.dumps(dict(version=1,sources=['allocation.c'],functions={
            'native_packet':dict(symbol='native_packet',params=[['data','borrowed_bytes']],result='bytes')})))
        obj=self.root/'packet.o'
        compiled=self.command('compile-c',source,'--interface',interface,'--c-api-name','packet','-o',obj)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        before=self.snapshot(obj)
        wrapper=self.write('packet.ail','''fn packet(data:bytes)->bytes { return native_packet(data); }
fn count(data:bytes)->int { return len(data); }
''')
        library=self.root/'library'
        built=self.command('compile-library',wrapper,'--name','packet','--object',obj,'-o',library)
        self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
        self.assertEqual(self.snapshot(obj),before)
        for path in (source,interface,wrapper,self.root/'allocation.c',obj,Path(str(obj)+'.json')):path.unlink()
        moved=self.root/'移動した library';library.rename(moved)
        consumer=self.write('consumer.c',r'''
#include "packet.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static long blocks,streams;
void *__real_malloc(size_t); void *__real_calloc(size_t,size_t);
void *__real_realloc(void *,size_t); void __real_free(void *);
FILE *__real_fopen(const char *,const char *); int __real_fclose(FILE *);
void *__wrap_malloc(size_t n) {void *p=__real_malloc(n);if(p)blocks++;return p;}
void *__wrap_calloc(size_t n,size_t s) {void *p=__real_calloc(n,s);if(p)blocks++;return p;}
void *__wrap_realloc(void *p,size_t n) {void *q=__real_realloc(p,n);if(!p&&q)blocks++;else if(p&&!n)blocks--;return q;}
void __wrap_free(void *p) {if(p)blocks--;__real_free(p);}
FILE *__wrap_fopen(const char *p,const char *m) {FILE *f=__real_fopen(p,m);if(f)streams++;return f;}
int __wrap_fclose(FILE *p) {streams--;return __real_fclose(p);}
int host_reenter(void) {
    packet_error error;int64_t result=77;
    int status=packet_count((packet_view){NULL,0},&result,&error);
    return result==77 && error.code==10 ? status : -1;
}
int main(void) {
    const long initial_blocks=blocks,initial_streams=streams;
    unsigned char input[65537];for(size_t i=0;i<sizeof input;i++)input[i]=(unsigned char)i;
    packet_error error;packet_buffer result;
    for(int repetition=0;repetition<30;repetition++) {
        result=(packet_buffer){(unsigned char*)input,19};
        if(packet_packet((packet_view){input,3},&result,&error)!=8 || error.code!=8 || result.data!=input || result.size!=19) return 1;
        if(blocks!=initial_blocks || streams!=initial_streams) return 2;
        for(size_t n=0;n<=sizeof input;n=n<17?n+1:sizeof input+1) {
            if(n==3)continue;
            if(packet_packet((packet_view){input,n},&result,&error) || result.size!=n) return 3;
            for(size_t i=0;i<n;i++)if(result.data[i]!=(unsigned char)(input[i]^255) || input[i]!=(unsigned char)i)return 4;
            packet_free(result.data);if(blocks!=initial_blocks || streams!=initial_streams)return 5;
        }
        if(packet_packet((packet_view){input,sizeof input},&result,&error) || result.size!=sizeof input) return 6;
        for(size_t i=0;i<sizeof input;i++)if(result.data[i]!=(unsigned char)(input[i]^255))return 7;
        packet_free(result.data);if(blocks!=initial_blocks || streams!=initial_streams)return 8;
    }
    printf("{\"baseline_allocations\":%ld,\"baseline_streams\":%ld,\"remaining_allocations\":%ld,\"remaining_streams\":%ld}\n",
           initial_blocks,initial_streams,blocks-initial_blocks,streams-initial_streams);
    return 0;
}
''')
        executable=self.root/('consumer.exe' if os.name=='nt' else 'consumer')
        compiled=subprocess.run([module_object.compiler(),*module_object.FLAGS,'-std=c11','-I','.',
            '../consumer.c','packet.o','-lm',*(f'-Wl,--wrap={fn}' for fn in
            ('malloc','calloc','realloc','free','fopen','fclose')),'-o','../'+executable.name],
            cwd=moved,capture_output=True,timeout=180)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        payload=self.root/'payload.dat';payload.write_bytes(b'file retained')
        result=subprocess.run([str(executable)],cwd=self.root,capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        metrics=json.loads(result.stdout)
        self.assertEqual((metrics['remaining_allocations'],metrics['remaining_streams']),(0,0))
        self.assertEqual(payload.read_bytes(),b'file retained')
        print(json.dumps(dict(profile='linked allocation and FILE counters; not RSS or speed',
            platform=sys.platform,repetitions=30,reentrant_status=10,**metrics)))

    @unittest.skipUnless(objcopy_available(),OBJCOPY_REASON)
    def test_crc_example_public_cli_closure(self):
        examples=support.ROOT/'language_examples/c_headers_workflow'
        native,stream=self.root/'native.o',self.root/'stream.o'
        exported=subprocess.run([sys.executable,'-X','utf8','-B',str(examples/'build_crc_library.py'),
            '--c-api-name','capicrc','--out',str(native)],capture_output=True,timeout=180)
        self.assertEqual(exported.returncode,0,exported.stderr.decode(errors='replace'))
        compiled=self.command('compile-module',examples/'crc32_stream.ail','--object',native,
            '--c-api-name','capicrc','-o',stream)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        before=self.snapshot(native,stream)
        library=self.root/'library'
        compiled=self.command('compile-library',examples/'crc_c_api.ail','--name','capicrc',
            '--object',native,'--object',stream,'-o',library)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        self.assertEqual(self.snapshot(native,stream),before)
        for obj in (native,stream):obj.unlink();Path(str(obj)+'.json').unlink()
        path=self.root/'入力.bin';data=bytes(range(256))*257+b'\xff';path.write_bytes(data)
        utf8=''.join('\\x%02x'%value for value in path.as_posix().encode('utf8'))
        consumer=self.write('example.c',f'''#include "capicrc.h"
int main(void) {{
 capicrc_error error;int64_t result=0;
 const unsigned char data[]={{0,255,128,65}};
 if(capicrc_update(0,(capicrc_view){{data,4}},&result,&error) || result!={zlib.crc32(bytes((0,255,128,65)))})return 1;
 const unsigned char path[]="{utf8}";
 if(capicrc_file_crc((capicrc_view){{path,sizeof path-1}},&result,&error) || result!={zlib.crc32(data)})return 2;
 return 0;
}}''')
        executable=self.root/('example.exe' if os.name=='nt' else 'example')
        compiled=subprocess.run([module_object.compiler(),'-std=c11','-I','.','../example.c','capicrc.o',
            '-lm','-o','../'+executable.name],cwd=library,capture_output=True,timeout=180)
        self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
        result=subprocess.run([str(executable)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))
        self.assertEqual(path.read_bytes(),data)


if __name__=='__main__':unittest.main()
