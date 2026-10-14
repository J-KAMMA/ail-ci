"""binary_cursor_records: sums of five unsigned fields over 13-byte records (u8, u16le, u16be, u32le, u32be)."""
import random
from pathlib import Path

AIL_SOURCE='language_examples/binary_cursor_records_main.ail'
AIL_OPTIONS=[]
STRATEGY=dict(ail='validate file size, then file_chunks of 65533 bytes (5041 records): a BinaryCursor per chunk, read_u8/u16/u32 per field',
              c='fread streaming into a 13*80000-byte (~1 MiB) buffer, whole records per chunk, tight decode loop, uint64 sums',
              rust='File::read into a 13*80000-byte (~1 MiB) buffer refilled to full, whole records per chunk, from_le/be_bytes decode, u64 sums')
REFERENCE_SCOPE='C/Rust use wrapping uint64 sums (exact below 2^64, no input here approaches it) and stream the file; AIL uses a whole-file read; a directory path is not exercised'

C_SOURCE=r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define REC 13
#define CHUNK (REC*80000)
static int fail(const char *m){fprintf(stderr,"%s\n",m);return 2;}
int main(int argc,char **argv){
    if(argc!=2)return fail("usage: binary_cursor_records input-path");
    FILE *f=fopen(argv[1],"rb");if(!f)return fail("binary record file error");
    unsigned char *buf=malloc(CHUNK);if(!buf)return fail("binary record file error");
    uint64_t count=0,s8=0,s16l=0,s16b=0,s32l=0,s32b=0,total=0;
    for(;;){
        size_t got=fread(buf,1,CHUNK,f);
        if(got==0)break;
        if(got%REC)return fail("invalid binary record input");
        total+=got;count+=got/REC;
        for(const unsigned char *p=buf,*e=buf+got;p<e;p+=REC){
            s8+=p[0];
            s16l+=(uint32_t)p[1]|(uint32_t)p[2]<<8;
            s16b+=(uint32_t)p[3]<<8|p[4];
            s32l+=(uint32_t)p[5]|(uint32_t)p[6]<<8|(uint32_t)p[7]<<16|(uint32_t)p[8]<<24;
            s32b+=(uint32_t)p[9]<<24|(uint32_t)p[10]<<16|(uint32_t)p[11]<<8|p[12];
        }
        if(got<CHUNK)break;
    }
    if(ferror(f))return fail("binary record file error");
    if(count>2147483648ULL)return fail("invalid binary record input");
    if(printf("%llu %llu %llu %llu %llu %llu %llu\n",(unsigned long long)count,(unsigned long long)s8,(unsigned long long)s16l,
              (unsigned long long)s16b,(unsigned long long)s32l,(unsigned long long)s32b,(unsigned long long)total)<0||fflush(stdout))
        return fail("output write failed");
    return 0;}
'''

RUST_SOURCE=r'''use std::{env, fs::File, io::{self, Read, Write}, process::exit};
const REC: usize = 13;
const CHUNK: usize = REC * 80000;
fn fail(m: &str) -> ! { eprintln!("{}", m); exit(2) }
fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() != 2 { fail("usage: binary_cursor_records input-path"); }
    let mut f = File::open(&a[1]).unwrap_or_else(|_| fail("binary record file error"));
    let mut buf = vec![0u8; CHUNK];
    let (mut count, mut s8, mut s16l, mut s16b, mut s32l, mut s32b, mut total) = (0u64, 0u64, 0u64, 0u64, 0u64, 0u64, 0u64);
    loop {
        let mut got = 0;
        while got < CHUNK {
            match f.read(&mut buf[got..]) {
                Ok(0) => break,
                Ok(n) => got += n,
                Err(ref e) if e.kind() == io::ErrorKind::Interrupted => {}
                Err(_) => fail("binary record file error"),
            }
        }
        if got % REC != 0 { fail("invalid binary record input"); }
        for r in buf[..got].chunks_exact(REC) {
            s8 += r[0] as u64;
            s16l += u16::from_le_bytes([r[1], r[2]]) as u64;
            s16b += u16::from_be_bytes([r[3], r[4]]) as u64;
            s32l += u32::from_le_bytes([r[5], r[6], r[7], r[8]]) as u64;
            s32b += u32::from_be_bytes([r[9], r[10], r[11], r[12]]) as u64;
        }
        count += (got / REC) as u64;
        total += got as u64;
        if got < CHUNK { break; }
    }
    if count > 2147483648 { fail("invalid binary record input"); }
    let out = io::stdout();
    let mut lock = out.lock();
    if writeln!(lock, "{} {} {} {} {} {} {}", count, s8, s16l, s16b, s32l, s32b, total).and_then(|_| lock.flush()).is_err() { fail("output write failed"); }
}
'''

def _fmt(count,sums,size):
    return (' '.join(map(str,(count,*sums,size)))+'\n').encode()

def _oracle(data):
    """Per-record decode with int.from_bytes (small inputs)."""
    sums=[0]*5
    for o in range(0,len(data),13):
        c=data[o:o+13]
        v=(c[0],int.from_bytes(c[1:3],'little'),int.from_bytes(c[3:5],'big'),int.from_bytes(c[5:9],'little'),int.from_bytes(c[9:13],'big'))
        sums=[a+b for a,b in zip(sums,v)]
    return _fmt(len(data)//13,sums,len(data))

def _oracle_lanes(data):
    """Large inputs: strided byte-lane sums, independent of the per-record decode."""
    n=len(data)//13
    lane=[sum(data[k:n*13:13]) for k in range(13)]
    sums=[lane[0],lane[1]+(lane[2]<<8),(lane[3]<<8)+lane[4],
          lane[5]+(lane[6]<<8)+(lane[7]<<16)+(lane[8]<<24),(lane[9]<<24)+(lane[10]<<16)+(lane[11]<<8)+lane[12]]
    return _fmt(n,sums,len(data))

def _record(i):
    v=(i&255,(i*73+17)&65535,(i*211+9)&65535,(i*2654435761+0x12345678)&0xffffffff,(i*2246822519+0x87654321)&0xffffffff)
    return bytes([v[0]])+v[1].to_bytes(2,'little')+v[2].to_bytes(2,'big')+v[3].to_bytes(4,'little')+v[4].to_bytes(4,'big')

def controls(work):
    work=Path(work);cases=[]
    samples=[('empty',b''),('one',_record(1)),('zero',bytes(13)),('max',bytes([255])*13),('max3',bytes([255])*39),
             ('several',b''.join(_record(i) for i in range(1000))),
             ('chunk',b''.join(_record(i) for i in range(80001))),
             ('mixed',bytes([255,0,0,0,255,255,255,255,255,0,0,0,0])+bytes([0,255,255,255,0,0,0,0,0,255,255,255,255]))]
    for name,data in samples:
        p=work/('rec_%s.bin'%name);p.write_bytes(data)
        cases.append(dict(name='ok_'+name,args=[str(p)],expect_exit=0,expected_stdout=_oracle(data)))
    for tail in (1,12):
        p=work/('rec_tail%d.bin'%tail);p.write_bytes(_record(7)+_record(9)[:tail])
        cases.append(dict(name='reject_tail%d'%tail,args=[str(p)],expect_exit='nonzero',stdout_empty=True))
    cases.append(dict(name='reject_missing',args=[str(work/'absent.bin')],expect_exit='nonzero',stdout_empty=True))
    cases.append(dict(name='reject_noargs',args=[],expect_exit='nonzero',stdout_empty=True))
    cases.append(dict(name='reject_extra',args=[str(work/'rec_one.bin'),'extra'],expect_exit='nonzero',stdout_empty=True))
    return cases

def generate(work,smoke):
    count=80000 if smoke else 4000000
    data=random.Random(835).randbytes(13*count)
    path=Path(work)/'records_large.bin';path.write_bytes(data)
    return dict(name='records_%d'%count,args=[str(path)],expect_exit=0,expected_stdout=_oracle_lanes(data))
