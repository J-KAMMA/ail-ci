"""numeric_scale_binary: scale a raw IEEE binary64 array by a finite factor, little or big endian, to stdout."""
import random, struct
from array import array
from pathlib import Path

AIL_SOURCE='language_examples/numeric_scale_binary_main.ail'
AIL_OPTIONS=[]
STRATEGY=dict(ail='validate file size, then stream 64 KiB file_chunks: unpack_float64, float_values_scale, pack_float64, stdout write per chunk',
              c='validate file size, then stream 1 MiB chunks: fread, multiply in place (bswap for big endian), fwrite',
              rust='validate file size, then stream 1 MiB chunks: read_exact, multiply in place, write_all to locked stdout')
REFERENCE_SCOPE=('C/Rust accept ASCII "0"/"1" order only (AIL also accepts signs, leading zeros and Unicode spaces) and ASCII '
                 'decimal factors via strtod/str::parse with non-finite results rejected (AIL float() syntax may differ); '
                 'little-endian host assumed; controls avoid NaN inputs and NaN-producing factors (NaN payload bits unspecified)')

C_SOURCE=r'''#define _GNU_SOURCE
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CH (1u<<17)
static int fail(const char *m,int c){fprintf(stderr,"%s\n",m);return c;}
int main(int argc,char **argv){
    if(argc!=4)return fail("usage",2);
    int big;
    if(!strcmp(argv[2],"0"))big=0;else if(!strcmp(argv[2],"1"))big=1;else return fail("invalid binary64 records, order or finite factor",2);
    char *end;const char *s=argv[3];
    if(!*s||isspace((unsigned char)*s))return fail("invalid binary64 records, order or finite factor",2);
    double factor=strtod(s,&end);
    if(*end||!isfinite(factor))return fail("invalid binary64 records, order or finite factor",2);
    FILE *f=fopen(argv[1],"rb");if(!f)return fail("binary64 input/output error",3);
    if(fseek(f,0,SEEK_END))return fail("binary64 input/output error",3);
    long size=ftell(f);if(size<0||fseek(f,0,SEEK_SET))return fail("binary64 input/output error",3);
    if(size%8)return fail("invalid binary64 records, order or finite factor",2);
    uint64_t *buf=malloc(CH*8);if(!buf)return fail("binary64 input/output error",3);
    for(long left=size/8;left>0;){
        size_t n=left<(long)CH?(size_t)left:CH;
        if(fread(buf,8,n,f)!=n)return fail("binary64 input/output error",3);
        for(size_t i=0;i<n;i++){
            uint64_t b=buf[i];if(big)b=__builtin_bswap64(b);
            double x;memcpy(&x,&b,8);x*=factor;memcpy(&b,&x,8);
            buf[i]=big?__builtin_bswap64(b):b;}
        if(fwrite(buf,8,n,stdout)!=n)return fail("binary64 input/output error",3);
        left-=(long)n;}
    if(fflush(stdout))return fail("binary64 input/output error",3);
    return 0;}
'''

RUST_SOURCE=r'''use std::{env, fs::File, io::{Read, Write, stdout}, process::exit};
const BAD: &str = "invalid binary64 records, order or finite factor";
const IO: &str = "binary64 input/output error";
fn fail(m: &str, c: i32) -> ! { eprintln!("{}", m); exit(c) }
fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() != 4 { fail("usage", 2); }
    let big = match a[2].as_str() { "0" => false, "1" => true, _ => fail(BAD, 2) };
    let factor: f64 = match a[3].parse() { Ok(v) if f64::is_finite(v) && !a[3].starts_with(char::is_whitespace) => v, _ => fail(BAD, 2) };
    let mut f = File::open(&a[1]).unwrap_or_else(|_| fail(IO, 3));
    let size = f.metadata().unwrap_or_else(|_| fail(IO, 3)).len() as usize;
    if size % 8 != 0 { fail(BAD, 2); }
    let out = stdout();
    let mut out = out.lock();
    let mut buf = vec![0u8; 1 << 20];
    let mut left = size;
    while left > 0 {
        let n = left.min(buf.len());
        f.read_exact(&mut buf[..n]).unwrap_or_else(|_| fail(IO, 3));
        for c in buf[..n].chunks_exact_mut(8) {
            let w: [u8; 8] = (&*c).try_into().unwrap();
            let x = if big { f64::from_be_bytes(w) } else { f64::from_le_bytes(w) } * factor;
            c.copy_from_slice(&if big { x.to_be_bytes() } else { x.to_le_bytes() });
        }
        out.write_all(&buf[..n]).unwrap_or_else(|_| fail(IO, 3));
        left -= n;
    }
    out.flush().unwrap_or_else(|_| fail(IO, 3));
}
'''

def _scale(data,prefix,factor):
    n=len(data)//8
    return struct.pack('%s%dd'%(prefix,n),*(x*factor for x in struct.unpack('%s%dd'%(prefix,n),data)))

def controls(work):
    work=Path(work);cases=[]
    special=[0.0,-0.0,1.0,-3.0,1e-300,1e300,2**-1022,2**-1074,-2**-1074,1.7976931348623157e308,-1.7976931348623157e308,
             float('inf'),float('-inf'),123456.789,5e-324*3]
    def add(name,data,order,factor,text=None):
        p=work/(name+'.bin');p.write_bytes(data);prefix='<>'[order]
        cases.append(dict(name=name,args=[str(p),str(order),text or repr(factor)],expect_exit=0,expected_stdout=_scale(data,prefix,factor)))
    add('empty',b'',0,0.5)
    add('le_special_half',struct.pack('<%dd'%len(special),*special),0,0.5)
    add('be_special_half',struct.pack('>%dd'%len(special),*special),1,0.5)
    add('le_negative',struct.pack('<%dd'%len(special),*special),0,-0.5,'-0.5')
    add('be_fraction',struct.pack('>%dd'%len(special),*special),1,1.000000119,'1.000000119')
    add('le_zero_factor',struct.pack('<5d',1.0,-2.5,0.0,-0.0,1e300),0,0.0,'0')
    add('le_overflow',struct.pack('<4d',1e308,-1e308,1.0,5e-324),0,1e10,'1e10')
    add('le_exp_factor',struct.pack('<4d',1.5,-3.0,2**-1074,7.0),0,2.5e-3,'2.5e-3')
    base=work/'base.bin';base.write_bytes(struct.pack('<4d',1.0,2.0,3.0,4.0))
    odd=work/'odd.bin';odd.write_bytes(struct.pack('<2d',1.0,2.0)+b'\1')
    short=work/'short.bin';short.write_bytes(b'12345678'[:7])
    rej=lambda name,args:cases.append(dict(name='reject_'+name,args=args,expect_exit='nonzero',stdout_empty=True))
    rej('size_not_multiple_of_8',[str(odd),'0','0.5']);rej('size_7',[str(short),'1','0.5'])
    rej('order_2',[str(base),'2','0.5']);rej('order_minus1',[str(base),'-1','0.5']);rej('order_text',[str(base),'x','0.5'])
    for t in ('nan','inf','-inf','abc','','1e999'):rej('factor_'+(t or 'empty'),[str(base),'0',t])
    rej('missing',[str(work/'absent.bin'),'0','0.5'])
    rej('argc0',[]);rej('argc2',[str(base),'0']);rej('argc4',[str(base),'0','0.5','x'])
    return cases

def generate(work,smoke):
    count=(1<<20)//8 if smoke else 4_000_000
    rnd=random.Random(835);scales=[10.0**e for e in range(-30,31)]
    vals=array('d',((rnd.random()-0.5)*scales[rnd.randrange(61)] for _ in range(count)))
    factor=1.000000119
    path=Path(work)/'large.bin';path.write_bytes(vals.tobytes())
    return dict(name='scale_le_%dvalues'%count,args=[str(path),'0','1.000000119'],expect_exit=0,
                expected_stdout=array('d',(x*factor for x in vals)).tobytes())
