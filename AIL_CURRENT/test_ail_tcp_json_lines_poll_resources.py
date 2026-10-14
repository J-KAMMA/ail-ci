"""Long-lived JSON poll service: complete output and tracked heap bound."""
import json
import os
import shutil
import socket
import subprocess
import sys
import unittest
import test_ail_c_objects as support
from test_ail_exception_resources import ALLOCATOR
from test_ail_tcp_listener import RunningServer
from test_json_query_cli import document, render

class JsonPollResourceTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write

    def test_many_frames_do_not_accumulate_receive_arena(self):
        from ail_chatgpt import _load_sources
        entry=self.write('entry.ail','use tcp_json_lines_poll;\n'
                         'fn run()->int { let listener=tcp_listen("127.0.0.1",0,1); '
                         'print(listener.local_port()); flush_stdout(); '
                         'try { let result=tcp_json_lines_poll(listener,1,3000,256,1); '
                         'if result.status!=0 { raise RuntimeError; } return result.frames; } '
                         'finally { listener.close(); } }')
        source=_load_sources(entry,module_only=True,module_paths=(support.ROOT/'language_examples',))[0]
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            generated=to_c(source,name='run',strict=True,library=True)
        finally:
            sys.path.pop(0)
        drain=('for(int64_t j=0;j<ail__blk_cache_n;j++)count_free(ail__blk_cache[j].p);'
               'ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in generated else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        host=r'''int main(void){long long result=run();DRAIN
 fprintf(stderr,"{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"frames\":%d}\n",result,live,live_bytes,peak_bytes,ail_cleanup_top!=NULL);
 return live||live_bytes||ail_cleanup_top?5:0;}'''.replace('DRAIN',drain)
        path=self.write('service.c',ALLOCATOR+generated+host)
        exe=self.root/('service.exe' if os.name=='nt' else 'service')
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        flags=['-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)]
        if os.name=='nt':flags.append('-lws2_32')
        else:flags.insert(0,'-D_POSIX_C_SOURCE=200809L')
        result=subprocess.run([cc,*flags],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
        frame=b' {"duplicate":1,"duplicate":-0.00e+02} '
        expected=(render(document(frame))+'\n').encode()
        peaks=[]
        for n in (16,512,4096):
            with RunningServer(exe) as server:
                with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:
                    peer.settimeout(8)
                    for _ in range(n):
                        peer.sendall(frame+b'\n'); response=bytearray()
                        while not response.endswith(b'\n'):
                            chunk=peer.recv(8192); self.assertTrue(chunk); response.extend(chunk)
                        self.assertEqual(bytes(response),expected)
                    peer.shutdown(socket.SHUT_WR); self.assertEqual(peer.recv(1),b'')
                out,err=server.finish()
            self.assertEqual(out,b''); measured=json.loads(err)
            self.assertEqual((measured['result'],measured['live'],measured['bytes'],measured['frames']),(n,0,0,0))
            peaks.append(measured['peak'])
        print(f'tracked service peaks 16/512/4096 frames: {peaks}',flush=True)
        self.assertLessEqual(peaks[2],peaks[1]+8192,f'late tracked peaks 512/4096 frames: {peaks}')

if __name__=='__main__':unittest.main()