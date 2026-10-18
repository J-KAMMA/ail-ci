"""Injected poll/clock failures verify remaining budget, snapshots and cleanup."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_ail_exception_resources import ALLOCATOR, ROOT

HOOKS=r'''
#include <stdint.h>
#include <errno.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef WSAPOLLFD control_fd;
static int control_poll(WSAPOLLFD *,ULONG,int);
static ULONGLONG control_tick(void);
#define WSAPoll control_poll
#define GetTickCount64 control_tick
#else
#include <poll.h>
#include <time.h>
typedef struct pollfd control_fd;
static int control_poll(struct pollfd *,nfds_t,int);
static int control_clock(clockid_t,struct timespec *);
#define poll control_poll
#define clock_gettime control_clock
#endif
static int mode,poll_calls,clock_calls,bad_control;
static void *input_peers;
static int64_t *input_masks;
'''
HOST=r'''
static int socket_open(ail_socket_handle handle) {
 struct sockaddr_storage address;
#ifdef _WIN32
 int length=sizeof address;
#else
 socklen_t length=sizeof address;
#endif
 return getsockname(handle,(struct sockaddr *)&address,&length)==0;
}
static ail_socket_handle captured_handles[2];
static int interrupt_poll(void) {
#ifdef _WIN32
 WSASetLastError(WSAEINTR);return SOCKET_ERROR;
#else
 errno=EINTR;return -1;
#endif
}
static int poll_impl(control_fd *fds,uintmax_t count,int timeout) {
 poll_calls++;
 if(count!=1||fds[0].fd!=captured_handles[0]){bad_control=1;return 0;}
 if(mode==0){
  ail_hlist_tcpsocket_clear(input_peers); input_masks[0]=0;
  if(!socket_open(captured_handles[0])||!socket_open(captured_handles[1]))bad_control=2;
  fds[0].revents=POLLIN;return 1;
 }
 if(mode==1||mode==2||mode==3||mode==4||mode==8){
  if(poll_calls==1){if(timeout!=(mode==3?0:mode==4?-1:100))bad_control=3;return interrupt_poll();}
  if(timeout!=(mode==4?-1:60))bad_control=4;
  fds[0].revents=POLLOUT;return 1;
 }
 if(mode==11||mode==12){fds[0].revents=mode==11?POLLHUP:POLLERR;return 1;}
 if(mode==5){fds[0].revents=POLLNVAL;return 1;}
 if(mode==6){fds[0].revents=POLLPRI;return 1;}
 if(mode==7){
#ifdef _WIN32
  WSASetLastError(WSAEBADF);return SOCKET_ERROR;
#else
  errno=EBADF;return -1;
#endif
 }
 bad_control=5;return 0;
}
static uint64_t tick_impl(void) {
 clock_calls++;
 if(clock_calls==1)return 10;
 return mode==2?110:mode==8?9:50;
}
#ifdef _WIN32
static int control_poll(WSAPOLLFD *fds,ULONG count,int timeout){return poll_impl(fds,count,timeout);}
static ULONGLONG control_tick(void){return tick_impl();}
#else
static int control_poll(struct pollfd *fds,nfds_t count,int timeout){return poll_impl(fds,count,timeout);}
static int control_clock(clockid_t id,struct timespec *out){(void)id;uint64_t ms=tick_impl();out->tv_sec=ms/1000;out->tv_nsec=(ms%1000)*1000000;return 0;}
#endif
static int one(int selected) {
 mode=selected;poll_calls=clock_calls=bad_control=0;
 uint8_t text[]={'1','2','7','.','0','.','0','.','1'};
 ail_str host={text,9,1};
 ail_tcpsocket *listener=ail_tcpsocket_listen(host,0,1);
 ail_tcpsocket *client=ail_tcpsocket_connect(host,ail_tcpsocket_local_port(listener));
 ail_tcpsocket *server=ail_tcpsocket_accept(listener);
 ail_hlist_tcpsocket *peers=ail_hlist_tcpsocket_new();
 ail_hlist_tcpsocket_push(peers,client);ail_hlist_tcpsocket_push(peers,listener);
 captured_handles[0]=client->handle;captured_handles[1]=listener->handle;
 ail_tcpsocket_release(client);ail_tcpsocket_release(listener);
 int64_t interests[]={selected==0?1:selected==9?0:3,0};
 input_peers=peers;input_masks=interests;
 ail_list out={count_malloc(sizeof(int64_t)),1,1};out.p[0]=99;
 volatile int caught=0;
 ail_exc_cleanup[++ail_exc_top]=ail_cleanup_top;
 if(!AIL_SETJMP(ail_exc_stack[ail_exc_top])){
  if(selected==10){
   ail_hlist_tcpsocket forged={1,INT64_C(2147483648),INT64_C(2147483648),(ail_tcpsocket **)16};
   ail_tcp_poll(&out,&forged,(int64_t *)16,INT64_C(2147483648),0);
  }else ail_tcp_poll(&out,peers,interests,2,selected==0?0:selected==3?0:selected==4?-1:100);
 }else {caught=ail_exc_code;ail_exception_store(&ail_exc_value,NULL,1);}
 --ail_exc_top;
 int expected_error=selected==10?AIL_EXC_VALUE:(selected>=5&&selected<=8?AIL_EXC_OS:0);
 int good=caught==expected_error&&!bad_control&&!ail_cleanup_top&&!ail_exc_value&&!ail_handled_value;
 if(expected_error)good=good&&out.n==1&&out.p[0]==99;
 else {
  int expected=(selected>=11?3:selected==0?1:selected==1||selected==4?2:0);
  good=good&&out.n==2&&out.p[0]==expected&&out.p[1]==0;
 }
 if(selected==0)good=good&&!socket_open(captured_handles[0])&&!socket_open(captured_handles[1]);
 if(selected==1)good=good&&poll_calls==2&&clock_calls==2;
 if(selected==2||selected==8)good=good&&poll_calls==1&&clock_calls==2;
 if(selected==3)good=good&&poll_calls==1&&clock_calls==0;
 if(selected==4)good=good&&poll_calls==2&&clock_calls==0;
 if(selected==9||selected==10)good=good&&poll_calls==0&&clock_calls==0;
 ail_list_free(&out);ail_hlist_tcpsocket_release(peers);ail_tcpsocket_release(server);
 return good&&live==0&&live_bytes==0;
}
int main(void){for(int i=0;i<=12;i++){if(!one(i)){fprintf(stderr,"control %d failed: calls=%d clock=%d bad=%d live=%zu bytes=%zu\n",i,poll_calls,clock_calls,bad_control,live,live_bytes);return 9;}}puts("13 controls passed");return 0;}
'''

class TcpPollResourceTests(unittest.TestCase):
    def test_interrupted_budget_snapshot_ignored_handles_error_atomicity_and_cleanup(self):
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            source='def anchor(n:int)->int:\n peers:list[tcpsocket]=[]\n ready=tcp_poll(peers,[],n)\n return len(ready)\n'
            generated=to_c(source,name='anchor',strict=True,library=True)
        finally:
            sys.path.pop(0)
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        with tempfile.TemporaryDirectory(prefix='ail-poll-controls-') as temporary:
            root=Path(temporary);path=root/'control.c';exe=root/('control.exe' if os.name=='nt' else 'control')
            path.write_text(HOOKS+ALLOCATOR+generated+HOST,encoding='utf8')
            flags=['-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)]
            if os.name=='nt':flags.append('-lws2_32')
            else:flags.insert(0,'-D_POSIX_C_SOURCE=200809L')
            result=subprocess.run([cc,*flags],capture_output=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[:3000].decode(errors='replace'))
            result=subprocess.run([str(exe)],capture_output=True,timeout=30)
            self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'13 controls passed\n',b''))

    def test_repeated_results_and_caught_errors_have_bounded_heap(self):
        from ail_syntax import translate
        source=r'''fn run(n:int)->int {
 let listener=tcp_listen("127.0.0.1",0,1); let peers=[listener]; let total:int=0;
 for i in range(n) {
  let result=tcp_poll(peers,[0],-1); total+=len(result)+result[0];
  try { tcp_poll(peers,[2],0); } except OSError { total+=1; }
  try { tcp_poll(peers,[],0); } except ValueError { total+=1; }
 }
 listener.close(); return total;
}'''
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            generated=to_c(translate(source,module=True,imports=[]),name='run',strict=True,library=True)
        finally:
            sys.path.pop(0)
        drain=('for(int64_t j=0;j<ail__blk_cache_n;j++)count_free(ail__blk_cache[j].p);'
               'ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in generated else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in generated else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host=r'''int main(void){int sizes[]={1,17,10000};for(int i=0;i<3;i++){
 peak_bytes=0;long long result=run(sizes[i]);DRAIN
 printf("%lld %zu %zu %d %zu\n",result,live,live_bytes,ail_cleanup_top!=NULL,peak_bytes);
 if(live||live_bytes||ail_cleanup_top)return 5;
 }return 0;}'''.replace('DRAIN',drain)
        cc=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        with tempfile.TemporaryDirectory(prefix='ail-poll-loop-') as temporary:
            root=Path(temporary);path=root/'loop.c';exe=root/('loop.exe' if os.name=='nt' else 'loop')
            path.write_text(ALLOCATOR+generated+host,encoding='utf8')
            flags=['-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)]
            if os.name=='nt':flags.append('-lws2_32')
            else:flags.insert(0,'-D_POSIX_C_SOURCE=200809L')
            result=subprocess.run([cc,*flags],capture_output=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[:3000].decode(errors='replace'))
            result=subprocess.run([str(exe)],capture_output=True,timeout=30)
            self.assertEqual((result.returncode,result.stderr),(0,b''),result.stdout)
            rows=[list(map(int,line.split())) for line in result.stdout.splitlines()]
            self.assertEqual(len(rows),3)
            for row,n in zip(rows,(1,17,10000)):
                self.assertEqual(row[:4],[3*n,0,0,0])
            self.assertGreater(rows[0][4],0)
            self.assertLessEqual(rows[2][4],rows[1][4],'poll temporaries must not accumulate')

if __name__=='__main__':unittest.main()