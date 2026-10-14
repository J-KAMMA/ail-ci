"""csv_table: strict CSV parse + per-key int64 aggregation (group mode), JSON array output."""
import csv
import io
import json
import random
import re
from pathlib import Path

AIL_SOURCE='language_examples/csv_table_main.ail'
AIL_OPTIONS=[]
STRATEGY=dict(ail='streaming: file_chunks of SIZE bytes (1 MiB in the workload) -> incremental UTF-8 and CSV decoders -> dict aggregation',
              c='fread whole file into one buffer, UTF-8 validation pass, then in-place byte state machine and open-addressing FNV-1a table; single fwrite of the JSON',
              rust='fs::read whole file, str::from_utf8 validation pass, then in-place byte state machine and HashMap with FNV-1a hasher; single locked write of the JSON')
REFERENCE_SCOPE=('C/Rust implement only `group` mode (project mode exits 2); SIZE is validated (positive int64) but ignored because they read the whole file; '
                 'they implement the AIL CSV grammar (quote in the middle of an unquoted field is an error, blank lines skipped, CR/LF/CRLF terminators) '
                 'and strict UTF-8, int64 parse (optional sign, ASCII digits) and checked int64 totals')
# group mode is the workload: it exercises the full CSV tokenizer, UTF-8 decoding, hashing of string keys and checked int64
# aggregation, while the output stays small so the measurement is dominated by parsing/aggregation rather than stdout writes.
KEY_COL,VALUE_COL,CHUNK=1,3,1<<20
SMOKE_ROWS,LARGE_ROWS=20000,30000

C_SOURCE=r'''#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail(const char *m){fprintf(stderr,"%s\n",m);return 2;}
static int parse_i64(const unsigned char *s,size_t n,int64_t *out){
    int neg=0;size_t i=0;if(n&&(s[0]=='+'||s[0]=='-')){neg=s[0]=='-';i=1;}
    if(i==n)return 0;
    uint64_t lim=neg?(uint64_t)INT64_MAX+1:(uint64_t)INT64_MAX,v=0;
    for(;i<n;i++){unsigned d=s[i]-'0';if(d>9||v>(lim-d)/10)return 0;v=v*10+d;}
    *out=neg?(int64_t)(0-v):(int64_t)v;return 1;}
static int utf8_ok(const unsigned char *s,size_t n){
    size_t i=0;
    while(i<n){
        while(i+8<=n){uint64_t w;memcpy(&w,s+i,8);if(w&0x8080808080808080ULL)break;i+=8;}
        if(i>=n)break;
        unsigned c=s[i];
        if(c<0x80){i++;continue;}
        if(c>=0xC2&&c<=0xDF){if(i+2>n||(s[i+1]&0xC0)!=0x80)return 0;i+=2;}
        else if(c>=0xE0&&c<=0xEF){
            if(i+3>n||(s[i+1]&0xC0)!=0x80||(s[i+2]&0xC0)!=0x80)return 0;
            if((c==0xE0&&s[i+1]<0xA0)||(c==0xED&&s[i+1]>0x9F))return 0;i+=3;}
        else if(c>=0xF0&&c<=0xF4){
            if(i+4>n||(s[i+1]&0xC0)!=0x80||(s[i+2]&0xC0)!=0x80||(s[i+3]&0xC0)!=0x80)return 0;
            if((c==0xF0&&s[i+1]<0x90)||(c==0xF4&&s[i+1]>0x8F))return 0;i+=4;}
        else return 0;}
    return 1;}
typedef struct{const unsigned char *k;size_t kl;uint64_t h;int64_t cnt,tot,mn,mx;}Group;
static Group *groups;static size_t ngroups,gcap;
static uint32_t *slots;static size_t scap;
static void rehash(size_t cap){
    free(slots);slots=calloc(cap,sizeof *slots);scap=cap;
    for(size_t g=0;g<ngroups;g++){size_t p=groups[g].h&(cap-1);while(slots[p])p=(p+1)&(cap-1);slots[p]=(uint32_t)g+1;}}
static int add(const unsigned char *k,size_t kl,int64_t v){
    uint64_t h=1469598103934665603ULL;for(size_t i=0;i<kl;i++)h=(h^k[i])*1099511628211ULL;
    size_t p=h&(scap-1);
    for(;slots[p];p=(p+1)&(scap-1)){
        Group *g=&groups[slots[p]-1];
        if(g->h==h&&g->kl==kl&&!memcmp(g->k,k,kl)){
            if(__builtin_add_overflow(g->tot,v,&g->tot))return 0;
            g->cnt++;if(v<g->mn)g->mn=v;if(v>g->mx)g->mx=v;return 1;}}
    if(ngroups==gcap){gcap=gcap?gcap*2:1024;groups=realloc(groups,gcap*sizeof *groups);if(!groups)exit(fail("out of memory"));}
    groups[ngroups]=(Group){k,kl,h,1,v,v,v};slots[p]=(uint32_t)++ngroups;
    if(ngroups*2>scap)rehash(scap*2);
    return 1;}
static unsigned char *ob;static size_t olen,ocap;
static void put(const void *s,size_t n){
    if(olen+n>ocap){while(olen+n>ocap)ocap=ocap?ocap*2:4096;ob=realloc(ob,ocap);if(!ob)exit(fail("out of memory"));}
    memcpy(ob+olen,s,n);olen+=n;}
static void puts_(const char *s){put(s,strlen(s));}
static void put_key(const unsigned char *k,size_t n){
    put("\"",1);
    for(size_t i=0;i<n;i++){
        unsigned char c=k[i];char t[8];
        switch(c){
        case '"':puts_("\\\"");break;case '\\':puts_("\\\\");break;case '\b':puts_("\\b");break;case '\f':puts_("\\f");break;
        case '\n':puts_("\\n");break;case '\r':puts_("\\r");break;case '\t':puts_("\\t");break;
        default:if(c<32){snprintf(t,sizeof t,"\\u%04x",c);puts_(t);}else put(&c,1);}}
    put("\"",1);}
static void put_num(const char *name,int64_t v){char t[64];snprintf(t,sizeof t,"%s%lld",name,(long long)v);puts_(t);}
int main(int argc,char **argv){
    if(argc!=5&&argc!=6)return fail("usage: csv_table group INPUT KEY_COLUMN VALUE_COLUMN SIZE");
    if(argc!=6||strcmp(argv[1],"group"))return fail("invalid csv_table mode or argument count");
    int64_t kc,vc,size;
    if(!parse_i64((unsigned char*)argv[3],strlen(argv[3]),&kc)||!parse_i64((unsigned char*)argv[4],strlen(argv[4]),&vc)||
       !parse_i64((unsigned char*)argv[5],strlen(argv[5]),&size)||kc<0||vc<0||size<=0)return fail("invalid column or chunk size");
    FILE *f=fopen(argv[2],"rb");if(!f)return fail("input read failed");
    size_t cap=1<<20,n=0;unsigned char *d=malloc(cap);
    for(;;){
        if(n==cap){cap*=2;d=realloc(d,cap);}
        if(!d)return fail("input read failed");
        size_t got=fread(d+n,1,cap-n,f);n+=got;if(!got)break;}
    if(ferror(f))return fail("input read failed");
    fclose(f);
    if(!utf8_ok(d,n))return fail("invalid UTF-8");
    rehash(4096);
    size_t w=0,fs=0,nf=0,ks=0,kl=0;int mode=0,skip_lf=0;int64_t val=0;
#define END_FIELD do{if(nf==(uint64_t)kc){ks=fs;kl=w-fs;}\
    if(nf==(uint64_t)vc&&!parse_i64(d+fs,w-fs,&val))return fail("invalid integer");nf++;fs=w;}while(0)
#define END_ROW do{END_FIELD;if(nf<=(uint64_t)kc||nf<=(uint64_t)vc)return fail("short row");\
    if(!add(d+ks,kl,val))return fail("integer overflow");nf=0;}while(0)
    for(size_t i=0;i<n;i++){
        unsigned char c=d[i];
        if(skip_lf){skip_lf=0;if(c=='\n')continue;}
        if(mode==2){if(c=='"')mode=3;else d[w++]=c;}
        else if(c==','||c=='\r'||c=='\n'){
            if(c==',')END_FIELD;else if(mode||nf)END_ROW;
            mode=0;fs=w;skip_lf=c=='\r';}
        else if(c=='"'){
            if(mode==3){d[w++]='"';mode=2;}else{if(mode)return fail("invalid CSV");mode=2;}}
        else{if(mode==3)return fail("invalid CSV");mode=1;d[w++]=c;}}
    if(mode==2)return fail("invalid CSV");
    if(mode||nf)END_ROW;
    put("[",1);
    for(size_t g=0;g<ngroups;g++){
        if(g)put(",",1);
        puts_("{\"key\":");put_key(groups[g].k,groups[g].kl);
        put_num(",\"count\":",groups[g].cnt);put_num(",\"total\":",groups[g].tot);
        put_num(",\"minimum\":",groups[g].mn);put_num(",\"maximum\":",groups[g].mx);put("}",1);}
    put("]\n",2);
    if(fwrite(ob,1,olen,stdout)!=olen||fflush(stdout))return fail("output write failed");
    return 0;}
'''

RUST_SOURCE=r'''use std::{collections::HashMap, env, fs, hash::{BuildHasherDefault, Hasher}, io::{self, Write}, process::exit};
fn fail(m: &str) -> ! { eprintln!("{}", m); exit(2) }
#[derive(Default)]
struct Fnv(u64);
impl Hasher for Fnv {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, b: &[u8]) {
        let mut h = if self.0 == 0 { 0xcbf29ce484222325 } else { self.0 };
        for &x in b { h = (h ^ x as u64).wrapping_mul(0x100000001b3); }
        self.0 = h;
    }
}
fn parse_i64(b: &[u8]) -> Option<i64> {
    let (neg, digits) = match b.first() { Some(b'-') => (true, &b[1..]), Some(b'+') => (false, &b[1..]), _ => (false, b) };
    if digits.is_empty() { return None; }
    let limit: u128 = if neg { 1u128 << 63 } else { (1u128 << 63) - 1 };
    let mut v: u128 = 0;
    for &d in digits {
        if !d.is_ascii_digit() { return None; }
        v = v * 10 + (d - b'0') as u128;
        if v > limit { return None; }
    }
    Some(if neg { (0i128 - v as i128) as i64 } else { v as i64 })
}
struct Group { count: i64, total: i64, min: i64, max: i64 }
fn quote(out: &mut Vec<u8>, k: &[u8]) {
    out.push(b'"');
    for &c in k {
        match c {
            b'"' => out.extend_from_slice(b"\\\""), b'\\' => out.extend_from_slice(b"\\\\"), 8 => out.extend_from_slice(b"\\b"),
            12 => out.extend_from_slice(b"\\f"), b'\n' => out.extend_from_slice(b"\\n"), b'\r' => out.extend_from_slice(b"\\r"),
            b'\t' => out.extend_from_slice(b"\\t"),
            c if c < 32 => out.extend_from_slice(format!("\\u{:04x}", c).as_bytes()),
            c => out.push(c),
        }
    }
    out.push(b'"');
}
#[allow(unused_assignments)]
fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() != 5 && a.len() != 6 { fail("usage: csv_table group INPUT KEY_COLUMN VALUE_COLUMN SIZE"); }
    if a.len() != 6 || a[1] != "group" { fail("invalid csv_table mode or argument count"); }
    let num = |s: &String| parse_i64(s.as_bytes()).unwrap_or_else(|| fail("invalid column or chunk size"));
    let (kc, vc, size) = (num(&a[3]), num(&a[4]), num(&a[5]));
    if kc < 0 || vc < 0 || size <= 0 { fail("invalid column or chunk size"); }
    let (kc, vc) = (kc as usize, vc as usize);
    let mut d = fs::read(&a[2]).unwrap_or_else(|_| fail("input read failed"));
    if std::str::from_utf8(&d).is_err() { fail("invalid UTF-8"); }
    let mut map: HashMap<Vec<u8>, usize, BuildHasherDefault<Fnv>> = HashMap::default();
    let mut groups: Vec<(Vec<u8>, Group)> = Vec::new();
    let (mut w, mut fs, mut nf, mut ks, mut kl) = (0usize, 0usize, 0usize, 0usize, 0usize);
    let (mut mode, mut skip_lf, mut val) = (0u8, false, 0i64);
    macro_rules! end_field { () => {{
        if nf == kc { ks = fs; kl = w - fs; }
        if nf == vc { val = parse_i64(&d[fs..w]).unwrap_or_else(|| fail("invalid integer")); }
        nf += 1; fs = w;
    }}; }
    macro_rules! end_row { () => {{
        end_field!();
        if nf <= kc || nf <= vc { fail("short row"); }
        let key = &d[ks..ks + kl];
        match map.get(key) {
            Some(&i) => { let g = &mut groups[i].1; g.total = g.total.checked_add(val).unwrap_or_else(|| fail("integer overflow"));
                          g.count += 1; g.min = g.min.min(val); g.max = g.max.max(val); }
            None => { map.insert(key.to_vec(), groups.len()); groups.push((key.to_vec(), Group { count: 1, total: val, min: val, max: val })); }
        }
        nf = 0;
    }}; }
    for i in 0..d.len() {
        let c = d[i];
        if skip_lf { skip_lf = false; if c == b'\n' { continue; } }
        if mode == 2 {
            if c == b'"' { mode = 3 } else { d[w] = c; w += 1; }
        } else if c == b',' || c == b'\r' || c == b'\n' {
            if c == b',' { end_field!(); } else if mode != 0 || nf != 0 { end_row!(); }
            mode = 0; skip_lf = c == b'\r';
        } else if c == b'"' {
            if mode == 3 { d[w] = b'"'; w += 1; mode = 2; } else { if mode != 0 { fail("invalid CSV"); } mode = 2; }
        } else {
            if mode == 3 { fail("invalid CSV"); }
            mode = 1; d[w] = c; w += 1;
        }
    }
    if mode == 2 { fail("invalid CSV"); }
    if mode != 0 || nf != 0 { end_row!(); }
    let mut out: Vec<u8> = Vec::with_capacity(groups.len() * 64 + 8);
    out.push(b'[');
    for (n, (k, g)) in groups.iter().enumerate() {
        if n > 0 { out.push(b','); }
        out.extend_from_slice(b"{\"key\":");
        quote(&mut out, k);
        out.extend_from_slice(format!(",\"count\":{},\"total\":{},\"minimum\":{},\"maximum\":{}}}", g.count, g.total, g.min, g.max).as_bytes());
    }
    out.extend_from_slice(b"]\n");
    let stdout = io::stdout();
    let mut lock = stdout.lock();
    if lock.write_all(&out).and_then(|_| lock.flush()).is_err() { fail("output write failed"); }
}
'''

MIN_I64,MAX_I64=-(1<<63),(1<<63)-1

def _integer(text):
    if not re.fullmatch(r'[+-]?[0-9]+',text):raise ValueError('strict ASCII decimal')
    value=int(text)
    if not MIN_I64<=value<=MAX_I64:raise ValueError('outside int64')
    return value

def _oracle(data,key_index,value_index):
    """Independent CPython oracle (strict csv.reader, json.dumps, strict int64 with overflow checks)."""
    rows=[row for row in csv.reader(io.StringIO(data.decode('utf8'),newline=''),strict=True) if row]
    groups={}
    for row in rows:
        key,value=row[key_index],_integer(row[value_index])
        if key not in groups:groups[key]=dict(key=key,count=0,total=0,minimum=value,maximum=value)
        group=groups[key];total=group['total']+value
        if not MIN_I64<=total<=MAX_I64:raise ValueError('intermediate total overflow')
        group.update(count=group['count']+1,total=total,minimum=min(group['minimum'],value),maximum=max(group['maximum'],value))
    return (json.dumps(list(groups.values()),ensure_ascii=False,separators=(',',':'))+'\n').encode()

def _rejected(data,key_index=0,value_index=1):
    try:_oracle(data,key_index,value_index)
    except Exception:return
    raise AssertionError('oracle accepted a data set meant to be rejected: %r'%data[:60])

def _keys():
    rng=random.Random(835)
    words=['Alpha','Beta','Gamma','Delta','東京','大阪','Zürich','São Paulo','Ñandú','日本語😀','Köln','Åre']
    keys=[]
    for i in range(1500):
        key='%s %s %d'%(rng.choice(words),rng.choice(words),i)
        kind=i%10
        if kind==3:key=key.replace(' ',', ',1)
        elif kind==5:key='He said "%s"'%key
        elif kind==7:key+='\nannex'
        quoted=kind in (3,5,7) or i%4==0
        keys.append('"%s"'%key.replace('"','""') if quoted else key)
    return keys

def _workload(rows):
    rng=random.Random(8350+rows)
    keys=_keys();nk=len(keys)
    picks=rng.choices(range(nk),k=rows)
    amounts=[rng.randrange(-1000000,1000001) for _ in range(rows)]
    parts=[]
    for i,(k,a) in enumerate(zip(picks,amounts)):
        parts.append('%d,%s,user%d,%s%d\n'%(i,keys[k],i%5000,'+' if i%97==0 and a>=0 else '',a))
    return ''.join(parts).encode()

def _case(name,data,path,columns,size,work):
    path=Path(work)/(path+'.csv');path.write_bytes(data)
    return dict(name=name,args=['group',str(path),str(columns[0]),str(columns[1]),str(size)],expect_exit=0,
                expected_stdout=_oracle(data,*columns))

def controls(work):
    work=Path(work);cases=[]
    accepted=[
        ('basic',('\n"日本語😀\x00",+0017,"a\r\nb"\r\nx,-3,q\nx,2,z\ny,9007199254740993,tail\n').encode(),(0,1),65536),
        ('chunk1_multibyte',('日本語😀,5\nÅre,-2\n日本語😀,7\n').encode(),(0,1),1),
        ('chunk7_quotes',('"a,b",1\r\n"he said ""hi""",2\n"a,b",3\n"line1\nline2",4\n').encode(),(0,1),7),
        ('empty_file',b'',(0,1),4096),
        ('blank_lines_only',b'\n\r\n\n',(0,1),4096),
        ('no_final_newline_crlf',b'k,1\r\nk,2\r\nj,3',(0,1),3),
        ('lone_cr_terminator',b'k,1\rk,2\rj,3\r',(0,1),4096),
        ('empty_key_and_fields',b',5,\n,6,x\n"",7,\n',(0,1),4096),
        ('reordered_columns',b'7,x,k\n8,y,k\n9,z,j\n',(2,0),4096),
        ('key_equals_value_column',b'5\n5\n-6\n',(0,0),4096),
        ('int64_endpoints',('low,%d,x\nhigh,%d,y\nlow,%d,z\nhigh,-1,z\n'%(MIN_I64,MAX_I64,0)).encode(),(0,1),4096),
        ('cancel_to_limit',('x,%d\nx,-1\nx,1\n'%MAX_I64).encode(),(0,1),4096),
        ('long_zero_int',('x,+'+'0'*1000+'7,tail\n').encode(),(0,1),4096),
        ('json_escapes',b'"a\tb\x01\x1f\x7f\\z\xe2\x80\xa8",1\n"q""r",2\n"a\tb\x01\x1f\x7f\\z\xe2\x80\xa8",3\n',(0,1),4096),
        ('first_seen_order',b'b,1\na,2\nb,3\nc,4\na,5\n',(0,1),4096),
    ]
    for name,data,columns,size in accepted:cases.append(_case(name,data,'ok_'+name,columns,size,work))
    ok=Path(work)/'ok_basic.csv'
    rejects=[('no_args',[]),('unknown_mode',['unknown',str(ok),'0','1','4096']),('missing_size',['group',str(ok),'0','1']),
             ('size_zero',['group',str(ok),'0','1','0']),('size_negative',['group',str(ok),'0','1','-1']),
             ('size_too_big',['group',str(ok),'0','1',str(MAX_I64+1)]),('negative_column',['group',str(ok),'-1','1','4096']),
             ('fullwidth_column',['group',str(ok),'１','1','4096']),('empty_column',['group',str(ok),'','1','4096']),
             ('extra_arg',['group',str(ok),'0','1','4096','x']),('missing_file',['group',str(Path(work)/'absent.csv'),'0','1','4096'])]
    cases+=[dict(name='reject_'+n,args=a,expect_exit='nonzero',stdout_empty=True) for n,a in rejects]
    bad=[('non_integer_value',b'key,bad\n'),('short_row',b'key,1\nmissing\n'),('invalid_utf8',b'key,1\nlate,\xff\n'),
         ('truncated_utf8',b'key,1\nlate,\xe6\x97'),('unterminated_quote',b'key,1\n"unterminated'),
         ('junk_after_quote',b'"a"b,1\n'),('empty_value',b'k,\n'),('value_out_of_range',b'k,9223372036854775808\n'),
         ('value_with_space',b'k, 1\n'),('total_overflow',('x,%d\nx,1\nx,-1\n'%MAX_I64).encode()),
         ('total_underflow',('x,%d\nx,-1\nx,1\n'%MIN_I64).encode()),('value_column_missing_late',b'k,1\nk\n')]
    for name,data in bad:
        _rejected(data) if name not in ('invalid_utf8','truncated_utf8') else None
        path=work/('bad_'+name+'.csv');path.write_bytes(data)
        cases.append(dict(name='reject_'+name,args=['group',str(path),'0','1','4096'],expect_exit='nonzero',stdout_empty=True))
    return cases

def generate(work,smoke):
    rows=SMOKE_ROWS if smoke else LARGE_ROWS
    data=_workload(rows);path=Path(work)/'large.csv';path.write_bytes(data)
    return dict(name='group_%drows_%dB'%(rows,len(data)),args=['group',str(path),str(KEY_COL),str(VALUE_COL),str(CHUNK)],
                expect_exit=0,expected_stdout=_oracle(data,KEY_COL,VALUE_COL))
