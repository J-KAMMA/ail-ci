"""binary_search: Python-bytes find/rfind/count/startswith/endswith over a whole file."""
import random
from pathlib import Path

AIL_SOURCE='language_examples/binary_search_main.ail'
AIL_OPTIONS=[]
STRATEGY=dict(ail='read_bytes whole file, library search',
              c='fread whole file, glibc memmem for find/count, backward memcmp for rfind',
              rust='fs::read whole file, first-byte position scan plus slice compare')
REFERENCE_SCOPE='C/Rust accept ASCII decimal int64 bounds and contiguous hex only; AIL also accepts Unicode-space ints and spaced hex'

C_SOURCE=r'''#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail(const char *m){fprintf(stderr,"%s\n",m);return 2;}
static int hexval(int c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static int parse_i64(const char *s,int64_t *out){
    int neg=0;if(*s=='+'||*s=='-'){neg=*s=='-';s++;}
    if(!*s)return 0;
    uint64_t limit=neg?(uint64_t)INT64_MAX+1:(uint64_t)INT64_MAX,v=0;
    for(;*s;s++){if(*s<'0'||*s>'9')return 0;unsigned d=*s-'0';if(v>(limit-d)/10)return 0;v=v*10+d;}
    *out=neg?(int64_t)(0-v):(int64_t)v;return 1;}
int main(int argc,char **argv){
    if(argc!=4&&argc!=6)return fail("usage");
    const char *mode=argv[1];int m=-1;const char *names[]={"find","rfind","count","startswith","endswith"};
    for(int i=0;i<5;i++)if(!strcmp(mode,names[i]))m=i;
    if(m<0)return fail("unknown search mode");
    size_t hl=strlen(argv[3]);if(hl%2)return fail("invalid hexadecimal needle or search range");
    unsigned char *needle=malloc(hl/2+1);size_t n=hl/2;
    for(size_t i=0;i<n;i++){int a=hexval(argv[3][2*i]),b=hexval(argv[3][2*i+1]);if(a<0||b<0)return fail("invalid hexadecimal needle or search range");needle[i]=(unsigned char)(a*16+b);}
    int64_t start=0,end=INT64_MAX;
    if(argc==6&&(!parse_i64(argv[4],&start)||!parse_i64(argv[5],&end)))return fail("invalid hexadecimal needle or search range");
    FILE *f=fopen(argv[2],"rb");if(!f)return fail("input read failed");
    size_t cap=1<<20,len=0;unsigned char *data=malloc(cap);
    for(;;){if(len==cap){cap*=2;data=realloc(data,cap);if(!data)return fail("input read failed");}
        size_t got=fread(data+len,1,cap-len,f);len+=got;if(got==0)break;}
    if(ferror(f))return fail("input read failed");fclose(f);
    int64_t L=(int64_t)len,result;
    if(end>L)end=L;else if(end<0){end+=L;if(end<0)end=0;}
    if(start<0){start+=L;if(start<0)start=0;}
    int bad=start>L||end-start<(int64_t)n;
    if(m==0){result=-1;if(!bad){if(!n)result=start;else{unsigned char *p=memmem(data+start,end-start,needle,n);if(p)result=p-data;}}}
    else if(m==1){result=-1;if(!bad){for(int64_t i=end-(int64_t)n;i>=start;i--)if(!memcmp(data+i,needle,n)){result=i;break;}}}
    else if(m==2){result=0;if(!bad){if(!n)result=end-start+1;else{unsigned char *p=data+start,*e=data+end;
        while((size_t)(e-p)>=n&&(p=memmem(p,e-p,needle,n))){result++;p+=n;}}}}
    else if(m==3)result=!bad&&!memcmp(data+start,needle,n);
    else result=!bad&&!memcmp(data+end-n,needle,n);
    if(printf("%lld\n",(long long)result)<0||fflush(stdout))return fail("output write failed");
    return 0;}
'''

RUST_SOURCE=r'''use std::{env, fs, io::{self, Write}, process::exit};
fn fail(m: &str) -> ! { eprintln!("{}", m); exit(2) }
fn parse_i64(s: &str) -> Option<i64> {
    let b = s.as_bytes();
    let (neg, digits) = match b.first() { Some(b'-') => (true, &b[1..]), Some(b'+') => (false, &b[1..]), _ => (false, b) };
    if digits.is_empty() || !digits.iter().all(u8::is_ascii_digit) { return None; }
    let limit: u128 = if neg { 1u128 << 63 } else { (1u128 << 63) - 1 };
    let mut v: u128 = 0;
    for d in digits { v = v * 10 + (d - b'0') as u128; if v > limit { return None; } }
    Some(if neg { (0i128 - v as i128) as i64 } else { v as i64 })
}
fn find_from(h: &[u8], n: &[u8]) -> Option<usize> {
    let mut i = 0;
    while h.len() - i >= n.len() {
        match h[i..=h.len() - n.len()].iter().position(|&c| c == n[0]) {
            None => return None,
            Some(k) => { let j = i + k; if &h[j..j + n.len()] == n { return Some(j); } i = j + 1; }
        }
    }
    None
}
fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() != 4 && a.len() != 6 { fail("usage"); }
    let m = ["find", "rfind", "count", "startswith", "endswith"].iter().position(|x| *x == a[1]).unwrap_or_else(|| fail("unknown search mode"));
    let hex = a[3].as_bytes();
    let bad_arg = "invalid hexadecimal needle or search range";
    if hex.len() % 2 != 0 { fail(bad_arg); }
    let needle: Vec<u8> = hex.chunks(2).map(|p| std::str::from_utf8(p).ok().filter(|s| s.bytes().all(|c| c.is_ascii_hexdigit()))
        .and_then(|s| u8::from_str_radix(s, 16).ok()).unwrap_or_else(|| fail(bad_arg))).collect();
    let (mut start, mut end) = (0i64, i64::MAX);
    if a.len() == 6 { start = parse_i64(&a[4]).unwrap_or_else(|| fail(bad_arg)); end = parse_i64(&a[5]).unwrap_or_else(|| fail(bad_arg)); }
    let data = fs::read(&a[2]).unwrap_or_else(|_| fail("input read failed"));
    let l = data.len() as i64; let n = needle.len() as i64;
    if end > l { end = l } else if end < 0 { end = (end + l).max(0) }
    if start < 0 { start = (start + l).max(0) }
    let bad = start > l || end - start < n;
    let (s, e) = (start.max(0) as usize, end.max(0) as usize);
    let result: i64 = match m {
        0 => if bad { -1 } else if n == 0 { start } else { find_from(&data[s..e], &needle).map_or(-1, |k| (s + k) as i64) },
        1 => if bad { -1 } else { (s..=e - needle.len()).rev().find(|&i| data[i..i + needle.len()] == needle[..]).map_or(-1, |i| i as i64) },
        2 => if bad { 0 } else if n == 0 { end - start + 1 } else {
            let (mut c, mut p) = (0i64, s);
            while let Some(k) = find_from(&data[p..e], &needle) { c += 1; p += k + needle.len(); }
            c },
        3 => (!bad && data[s..s + needle.len()] == needle[..]) as i64,
        _ => (!bad && data[e - needle.len()..e] == needle[..]) as i64,
    };
    let out = io::stdout();
    let mut lock = out.lock();
    if writeln!(lock, "{}", result).and_then(|_| lock.flush()).is_err() { fail("output write failed"); }
}
'''

def _expect(data,mode,needle,bounds=()):
    return ('%d\n'%int(getattr(data,mode)(needle,*map(int,bounds)))).encode()

def controls(work):
    path=Path(work)/'controls.bin';cases=[]
    samples=[(b'',b'',()),(b'aaaaa',b'aa',()),(b'\0\xff\x80\r\n'+bytes(range(256)),b'\0\xff',()),(b'aaa',b'a',(4,2)),
             (b'abc',b'',(3,3)),(b'abc',b'',(-9,-1)),(b'abc',b'bc',(-2,9)),
             (b'\0abc\xff',b'a',(-9223372036854775808,9223372036854775807)),(b'\0abc\xff',b'a',(9223372036854775807,9223372036854775807)),
             (b'\0abc\xff',b'a',(0,-9223372036854775808)),((bytes(range(256))*300)[:65537],b'\xfe\xff\0',(-65540,9223372036854775807))]
    for i,(data,needle,bounds) in enumerate(samples):
        p=Path(work)/('control%d.bin'%i);p.write_bytes(data)
        for mode in ('find','rfind','count','startswith','endswith'):
            cases.append(dict(name='%s_%d'%(mode,i),args=[mode,str(p),needle.hex(),*map(str,bounds)],expect_exit=0,
                              expected_stdout=_expect(data,mode,needle,bounds)))
    path.write_bytes(bytes(range(256)))
    for args in ([],['unknown',str(path),''],['find',str(path),'0'],['count',str(path),'GG'],['find',str(path),'00','x','5'],
                 ['find',str(path),'00','1'],['rfind',str(Path(work)/'absent'),'ff'],['find',str(path),'00','9223372036854775808','5']):
        cases.append(dict(name='reject_'+'_'.join(args[:1]+[str(len(args))]),args=args,expect_exit='nonzero',stdout_empty=True))
    return cases

def generate(work,smoke):
    size=(1<<20) if smoke else (64<<20)
    data=random.Random(835).randbytes(size).translate(bytes(b'ACGT'[i%4] for i in range(256)))
    path=Path(work)/'large.bin';path.write_bytes(data);needle=b'ACGTACG'
    return dict(name='count_%dB'%size,args=['count',str(path),needle.hex()],expect_exit=0,
                expected_stdout=_expect(data,'count',needle))
