"""json_query: strict RFC 8259 validation of a whole file, then RFC 6901 pointer batch extraction to an output file."""
import json
import random
import re
from pathlib import Path

AIL_SOURCE='language_examples/json_query_main.ail'
AIL_OPTIONS=['--object','{work}/file_identity.o']
STRATEGY=dict(ail='library json_query_file: whole-document strict parse/validation, then pointer selection and compact re-rendering to OUTPUT',
              c='fread whole file into one zero-padded buffer, single-pass recursive validating parser (UTF-8, escapes, numbers; no DOM) that resolves all pointers inside the same pass with per-pointer cursors and records value spans, then streaming compact render of the spans into one output buffer written once at the end',
              rust='read whole file into one zero-padded Vec, same single-pass validating parser with pointer cursors on bounds-checked slice indexing (no DOM), compact render of recorded spans into a Vec<u8> written once with fs::write')
REFERENCE_SCOPE=('C/Rust implement modes extract (exactly one pointer) and batch (zero or more pointers) with positional INPUT OUTPUT POINTER args only; '
                 'string-map mode, --input/--output/--pointer named options, --help and output-aliases-input refusal are AIL-only and not implemented or tested; '
                 'nesting depth is capped at 10000 in the references (AIL limit unspecified, not exercised); all errors exit 2 with no output file')

def _root():
    return next(p/'AIL_CURRENT' for p in Path(__file__).resolve().parents if (p/'AIL_CURRENT/ail_chatgpt.py').is_file())

def prepare_ail(work,cli):
    examples=_root()/'language_examples'
    cli('compile-c',examples/'file_identity.c','--interface',examples/'file_identity.json','-o',Path(work)/'file_identity.o')

C_SOURCE=r'''#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
typedef unsigned char u8;
#define MAXD 10000
#define PAD 16
static void die(const char *m){fprintf(stderr,"%s\n",m);exit(2);}
static u8 *buf,*out;static size_t outlen,outcap;
static void reserve(size_t n){if(outlen+n>outcap){while(outlen+n>outcap)outcap=outcap?outcap*2:1<<16;out=realloc(out,outcap);if(!out)die("out of memory");}}
static void put(u8 c){reserve(1);out[outlen++]=c;}
static const u8 *ws(const u8 *p){while(*p==' '||*p=='\n'||*p=='\r'||*p=='\t')p++;return p;}
static int hex4(const u8 *p){int v=0;for(int i=0;i<4;i++){int c=p[i],d;
    if(c>='0'&&c<='9')d=c-'0';else if((c|32)>='a'&&(c|32)<='f')d=(c|32)-'a'+10;else return -1;v=v*16+d;}return v;}
static int cont(u8 c){return (c&0xc0)==0x80;}
/* Validating pass. The buffer is followed by zero padding; a NUL byte is never valid JSON, so reads past the end fail naturally. */
static const u8 *vstring(const u8 *p){
    for(;;){u8 c=*p;
        if(c=='"')return p+1;
        if(c<0x20)die("invalid JSON string");
        if(c=='\\'){
            switch(p[1]){case '"':case '\\':case '/':case 'b':case 'f':case 'n':case 'r':case 't':p+=2;break;
            case 'u':{int h=hex4(p+2);if(h<0||(h>=0xdc00&&h<=0xdfff))die("invalid escape");p+=6;
                if(h>=0xd800&&h<=0xdbff){int l;if(p[0]!='\\'||p[1]!='u'||(l=hex4(p+2))<0xdc00||l>0xdfff)die("lone surrogate");p+=6;}
                break;}
            default:die("invalid escape");}
        }else if(c<0x80)p++;
        else if(c>=0xc2&&c<=0xdf){if(!cont(p[1]))die("invalid UTF-8");p+=2;}
        else if(c>=0xe0&&c<=0xef){if(!cont(p[1])||!cont(p[2])||(c==0xe0&&p[1]<0xa0)||(c==0xed&&p[1]>=0xa0))die("invalid UTF-8");p+=3;}
        else if(c>=0xf0&&c<=0xf4){if(!cont(p[1])||!cont(p[2])||!cont(p[3])||(c==0xf0&&p[1]<0x90)||(c==0xf4&&p[1]>=0x90))die("invalid UTF-8");p+=4;}
        else die("invalid UTF-8");}}
static const u8 *digits(const u8 *p){if(*p<'0'||*p>'9')die("invalid number");while(*p>='0'&&*p<='9')p++;return p;}
static const u8 *vnumber(const u8 *p){
    if(*p=='-')p++;
    if(*p=='0')p++;else p=digits(p);
    if(*p=='.')p=digits(p+1);
    if(*p=='e'||*p=='E'){p++;if(*p=='+'||*p=='-')p++;p=digits(p);}
    return p;}
static const u8 *lit(const u8 *p,const char *s,size_t n){if(memcmp(p,s,n))die("invalid literal");return p+n;}
/* Rendering over validated bytes: no checking, only structure. */
static const u8 *sstr(const u8 *p){for(;;){u8 c=*p++;if(c=='"')return p;if(c=='\\')p++;}}
static const u8 *sval(const u8 *p){while(*p>' '&&*p!=','&&*p!=']'&&*p!='}')p++;return p;}
/* Decodes a validated string body to UTF-8; esc=1 applies Python json.dumps(ensure_ascii=False) escaping. Output never exceeds input. */
static u8 *emit(u8 *o,unsigned cp,int esc){
    if(esc&&(cp<0x20||cp=='"'||cp=='\\')){*o++='\\';
        switch(cp){case '"':*o++='"';break;case '\\':*o++='\\';break;case '\n':*o++='n';break;case '\r':*o++='r';break;case '\t':*o++='t';break;
        case '\b':*o++='b';break;case '\f':*o++='f';break;
        default:*o++='u';*o++='0';*o++='0';*o++="0123456789abcdef"[cp>>4];*o++="0123456789abcdef"[cp&15];}
        return o;}
    if(cp<0x80)*o++=cp;
    else if(cp<0x800){*o++=0xc0|cp>>6;*o++=0x80|(cp&63);}
    else if(cp<0x10000){*o++=0xe0|cp>>12;*o++=0x80|((cp>>6)&63);*o++=0x80|(cp&63);}
    else{*o++=0xf0|cp>>18;*o++=0x80|((cp>>12)&63);*o++=0x80|((cp>>6)&63);*o++=0x80|(cp&63);}
    return o;}
static u8 *decode(const u8 *s,const u8 *e,u8 *o,int esc){
    while(s<e){
        if(*s!='\\'){const u8 *r=s;while(r<e&&*r!='\\')r++;memcpy(o,s,r-s);o+=r-s;s=r;continue;}
        switch(s[1]){case 'b':o=emit(o,8,esc);s+=2;break;case 'f':o=emit(o,12,esc);s+=2;break;case 'n':o=emit(o,10,esc);s+=2;break;
        case 'r':o=emit(o,13,esc);s+=2;break;case 't':o=emit(o,9,esc);s+=2;break;
        case 'u':{unsigned cp=hex4(s+2);s+=6;if(cp>=0xd800&&cp<=0xdbff){cp=0x10000+((cp-0xd800)<<10)+(hex4(s+2)-0xdc00);s+=6;}o=emit(o,cp,esc);break;}
        default:o=emit(o,s[1],esc);s+=2;}}
    return o;}
static void rstr(const u8 *s,const u8 *e){reserve((e-s)+3);out[outlen++]='"';outlen=decode(s,e,out+outlen,1)-out;out[outlen++]='"';}
static const u8 *rval(const u8 *p){
    if(*p=='"'){const u8 *e=sstr(p+1);rstr(p+1,e-1);return e;}
    if(*p=='{'||*p=='['){u8 open=*p,close=open=='{'?'}':']';put(open);p=ws(p+1);if(*p==close){put(close);return p+1;}
        for(;;){p=ws(p);
            if(open=='{'){const u8 *e=sstr(p+1);rstr(p+1,e-1);p=ws(ws(e)+1);put(':');}
            p=ws(rval(p));if(*p==','){put(',');p++;continue;}put(close);return p+1;}}
    const u8 *e=sval(p);reserve(e-p);memcpy(out+outlen,p,e-p);outlen+=e-p;return e;}
/* Pointers are resolved inside the validating pass: a cursor (pointer, token level) follows each pointer down the document. */
typedef struct{u8 *s;size_t l;int64_t idx;}Tok;   /* idx: array index, -1 not an RFC 6901 index, INT64_MAX too large */
typedef struct{Tok *t;int nt;const u8 *start,*end;}Ptr;
typedef struct{int p,k;}Cur;
static Ptr *P;
static void parse_ptr(Ptr *pp,const char *ptr){
    pp->nt=0;pp->t=NULL;
    if(!*ptr)return;
    if(*ptr!='/')die("plain JSON pointer required");
    int n=1;for(const char *q=ptr;*q;q++){if(*q=='~'&&q[1]!='0'&&q[1]!='1')die("invalid pointer escape");n+=*q=='/';}
    pp->t=calloc(n,sizeof(Tok));
    while(*ptr=='/'){
        const char *s=++ptr;while(*ptr&&*ptr!='/')ptr++;
        Tok *t=&pp->t[pp->nt++];t->s=malloc(ptr-s+1);t->l=0;
        for(const char *q=s;q<ptr;q++){if(*q=='~'){q++;t->s[t->l++]=*q=='0'?'~':'/';}else t->s[t->l++]=*q;}
        t->idx=-1;int dig=t->l>0&&(t->l==1||t->s[0]!='0');
        for(size_t i=0;i<t->l;i++)dig&=t->s[i]>='0'&&t->s[i]<='9';
        if(dig){t->idx=0;if(t->l>18)t->idx=INT64_MAX;else for(size_t i=0;i<t->l;i++)t->idx=t->idx*10+(t->s[i]-'0');}
    }}
static int keyeq(const u8 *ks,const u8 *ke,const Tok *t){
    if(!memchr(ks,'\\',ke-ks))return (size_t)(ke-ks)==t->l&&!memcmp(ks,t->s,t->l);
    static u8 *tmp;static size_t cap;
    if((size_t)(ke-ks)>cap){cap=ke-ks;tmp=realloc(tmp,cap);}
    size_t n=decode(ks,ke,tmp,0)-tmp;return n==t->l&&!memcmp(tmp,t->s,n);}
static const u8 *vvalue(const u8 *p,int depth,const Cur *cur,int n){
    if(depth>MAXD)die("too deep");
    p=ws(p);const u8 *s=p,*e;
    Cur sub[n+1];int done[n+1],ns=0,nd=0;
    for(int i=0;i<n;i++){if(cur[i].k==P[cur[i].p].nt)done[nd++]=cur[i].p;else sub[ns++]=cur[i];}
    switch(*p){
    case '{':{int cnt[ns+1];memset(cnt,0,sizeof cnt);p=ws(p+1);
        if(*p=='}')e=p+1;
        else for(;;){p=ws(p);if(*p!='"')die("invalid object");
            const u8 *ks=p+1;p=vstring(ks);const u8 *ke=p-1;p=ws(p);if(*p!=':')die("invalid object");
            Cur child[ns+1];int nc=0;
            for(int i=0;i<ns;i++)if(keyeq(ks,ke,&P[sub[i].p].t[sub[i].k])){cnt[i]++;child[nc].p=sub[i].p;child[nc++].k=sub[i].k+1;}
            p=ws(vvalue(p+1,depth+1,child,nc));
            if(*p==','){p++;continue;}if(*p=='}'){e=p+1;break;}die("invalid object");}
        for(int i=0;i<ns;i++)if(cnt[i]!=1)die("JSON pointer member missing or ambiguous");
        break;}
    case '[':{int64_t count=0;p=ws(p+1);
        for(int i=0;i<ns;i++)if(P[sub[i].p].t[sub[i].k].idx<0)die("invalid array index");
        if(*p==']')e=p+1;
        else for(;;count++){Cur child[ns+1];int nc=0;
            for(int i=0;i<ns;i++)if(P[sub[i].p].t[sub[i].k].idx==count){child[nc].p=sub[i].p;child[nc++].k=sub[i].k+1;}
            p=ws(vvalue(p,depth+1,child,nc));
            if(*p==','){p++;continue;}if(*p==']'){e=p+1;count++;break;}die("invalid array");}
        for(int i=0;i<ns;i++)if(P[sub[i].p].t[sub[i].k].idx>=count)die("array index outside the document");
        break;}
    default:
        if(*p=='"')e=vstring(p+1);else if(*p=='t')e=lit(p,"true",4);else if(*p=='f')e=lit(p,"false",5);
        else if(*p=='n')e=lit(p,"null",4);else e=vnumber(p);
        if(ns)die("JSON pointer target is missing");}
    for(int i=0;i<nd;i++){P[done[i]].start=s;P[done[i]].end=e;}
    return e;}
int main(int argc,char **argv){
    if(argc<4)die("usage: json_query extract|batch INPUT OUTPUT [POINTER ...]");
    int batch=!strcmp(argv[1],"batch");
    if(!batch&&(strcmp(argv[1],"extract")||argc!=5))die("invalid JSON query options");
    FILE *f=fopen(argv[2],"rb");if(!f)die("JSON query file error");
    int np=argc-4;P=calloc(np+1,sizeof(Ptr));Cur *init=malloc((np+1)*sizeof(Cur));
    for(int i=0;i<np;i++){parse_ptr(&P[i],argv[4+i]);init[i].p=i;init[i].k=0;}
    struct stat st;size_t cap=(fstat(fileno(f),&st)==0&&st.st_size>0?(size_t)st.st_size:1<<16)+2*PAD,len=0;
    buf=malloc(cap);if(!buf)die("out of memory");
    for(;;){if(len+PAD>=cap){cap*=2;buf=realloc(buf,cap);if(!buf)die("out of memory");}
        size_t got=fread(buf+len,1,cap-PAD-len,f);len+=got;if(!got)break;}
    if(ferror(f))die("JSON query file error");fclose(f);
    memset(buf+len,0,PAD);
    const u8 *p=ws(vvalue(buf,0,init,np));if(p!=buf+len)die("invalid JSON document");
    if(batch)put('[');
    for(int i=0;i<np;i++){if(i)put(',');if(!P[i].start)die("JSON pointer target is missing");rval(P[i].start);}
    if(batch)put(']');
    put('\n');
    FILE *o=fopen(argv[3],"wb");
    if(!o)die("JSON query file error");
    if(fwrite(out,1,outlen,o)!=outlen||fclose(o))die("JSON query file error");
    return 0;}
'''

RUST_SOURCE=r'''use std::{env, fs, io::Read, process::exit};
fn fail(m: &str) -> ! { eprintln!("{}", m); exit(2) }
const MAXD: usize = 10000;
const PAD: usize = 16;
fn ws(d: &[u8], mut p: usize) -> usize { while matches!(d[p], b' ' | b'\n' | b'\r' | b'\t') { p += 1; } p }
fn hex4(d: &[u8], p: usize) -> i32 {
    let mut v = 0;
    for i in 0..4 {
        let c = d[p + i];
        let x = match c { b'0'..=b'9' => c - b'0', b'a'..=b'f' => c - b'a' + 10, b'A'..=b'F' => c - b'A' + 10, _ => return -1 };
        v = v * 16 + x as i32;
    }
    v
}
fn cont(c: u8) -> bool { c & 0xc0 == 0x80 }
// Validating pass. d is followed by zero padding; NUL is never valid JSON, so reads past the end fail naturally.
fn vstring(d: &[u8], mut p: usize) -> usize {
    loop {
        let c = d[p];
        if c == b'"' { return p + 1; }
        if c < 0x20 { fail("invalid JSON string"); }
        if c == b'\\' {
            match d[p + 1] {
                b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't' => p += 2,
                b'u' => {
                    let h = hex4(d, p + 2);
                    if h < 0 || (0xdc00..=0xdfff).contains(&h) { fail("invalid escape"); }
                    p += 6;
                    if (0xd800..=0xdbff).contains(&h) {
                        if d[p] != b'\\' || d[p + 1] != b'u' { fail("lone surrogate"); }
                        let l = hex4(d, p + 2);
                        if !(0xdc00..=0xdfff).contains(&l) { fail("lone surrogate"); }
                        p += 6;
                    }
                }
                _ => fail("invalid escape"),
            }
        } else if c < 0x80 { p += 1; }
        else if (0xc2..=0xdf).contains(&c) { if !cont(d[p + 1]) { fail("invalid UTF-8"); } p += 2; }
        else if (0xe0..=0xef).contains(&c) {
            if !cont(d[p + 1]) || !cont(d[p + 2]) || (c == 0xe0 && d[p + 1] < 0xa0) || (c == 0xed && d[p + 1] >= 0xa0) { fail("invalid UTF-8"); }
            p += 3;
        } else if (0xf0..=0xf4).contains(&c) {
            if !cont(d[p + 1]) || !cont(d[p + 2]) || !cont(d[p + 3]) || (c == 0xf0 && d[p + 1] < 0x90) || (c == 0xf4 && d[p + 1] >= 0x90) { fail("invalid UTF-8"); }
            p += 4;
        } else { fail("invalid UTF-8"); }
    }
}
fn digits(d: &[u8], mut p: usize) -> usize {
    if !d[p].is_ascii_digit() { fail("invalid number"); }
    while d[p].is_ascii_digit() { p += 1; }
    p
}
fn vnumber(d: &[u8], mut p: usize) -> usize {
    if d[p] == b'-' { p += 1; }
    if d[p] == b'0' { p += 1; } else { p = digits(d, p); }
    if d[p] == b'.' { p = digits(d, p + 1); }
    if d[p] == b'e' || d[p] == b'E' {
        p += 1;
        if d[p] == b'+' || d[p] == b'-' { p += 1; }
        p = digits(d, p);
    }
    p
}
fn lit(d: &[u8], p: usize, s: &[u8]) -> usize { if &d[p..p + s.len()] != s { fail("invalid literal"); } p + s.len() }
// Rendering over validated bytes: no checking, only structure.
fn sstr(d: &[u8], mut p: usize) -> usize {
    loop { let c = d[p]; p += 1; if c == b'"' { return p; } if c == b'\\' { p += 1; } }
}
fn sval(d: &[u8], mut p: usize) -> usize { while d[p] > b' ' && !matches!(d[p], b',' | b']' | b'}') { p += 1; } p }
// Decodes a validated string body to UTF-8; esc applies Python json.dumps(ensure_ascii=False) escaping.
fn emit(o: &mut Vec<u8>, cp: u32, esc: bool) {
    if esc && (cp < 0x20 || cp == 0x22 || cp == 0x5c) {
        o.push(b'\\');
        match cp {
            0x22 => o.push(b'"'), 0x5c => o.push(b'\\'), 10 => o.push(b'n'), 13 => o.push(b'r'), 9 => o.push(b't'), 8 => o.push(b'b'), 12 => o.push(b'f'),
            _ => o.extend_from_slice(format!("u00{:02x}", cp).as_bytes()),
        }
        return;
    }
    let mut b = [0u8; 4];
    o.extend_from_slice(char::from_u32(cp).unwrap().encode_utf8(&mut b).as_bytes());
}
fn decode(d: &[u8], mut s: usize, e: usize, o: &mut Vec<u8>, esc: bool) {
    while s < e {
        if d[s] != b'\\' {
            let r = d[s..e].iter().position(|&c| c == b'\\').map_or(e, |k| s + k);
            o.extend_from_slice(&d[s..r]);
            s = r;
            continue;
        }
        match d[s + 1] {
            b'b' => { emit(o, 8, esc); s += 2 } b'f' => { emit(o, 12, esc); s += 2 } b'n' => { emit(o, 10, esc); s += 2 }
            b'r' => { emit(o, 13, esc); s += 2 } b't' => { emit(o, 9, esc); s += 2 }
            b'u' => {
                let mut cp = hex4(d, s + 2) as u32;
                s += 6;
                if (0xd800..=0xdbff).contains(&cp) { cp = 0x10000 + ((cp - 0xd800) << 10) + (hex4(d, s + 2) as u32 - 0xdc00); s += 6; }
                emit(o, cp, esc);
            }
            c => { emit(o, c as u32, esc); s += 2 }
        }
    }
}
fn rstr(d: &[u8], s: usize, e: usize, o: &mut Vec<u8>) { o.push(b'"'); decode(d, s, e, o, true); o.push(b'"'); }
fn rval(d: &[u8], mut p: usize, o: &mut Vec<u8>) -> usize {
    match d[p] {
        b'"' => { let e = sstr(d, p + 1); rstr(d, p + 1, e - 1, o); e }
        b'{' | b'[' => {
            let open = d[p];
            let close = if open == b'{' { b'}' } else { b']' };
            o.push(open);
            p = ws(d, p + 1);
            if d[p] == close { o.push(close); return p + 1; }
            loop {
                p = ws(d, p);
                if open == b'{' {
                    let e = sstr(d, p + 1);
                    rstr(d, p + 1, e - 1, o);
                    p = ws(d, ws(d, e) + 1);
                    o.push(b':');
                }
                p = ws(d, rval(d, p, o));
                if d[p] == b',' { o.push(b','); p += 1; continue; }
                o.push(close);
                return p + 1;
            }
        }
        _ => { let e = sval(d, p); o.extend_from_slice(&d[p..e]); e }
    }
}
// Pointers are resolved inside the validating pass: a cursor (pointer, token level) follows each pointer down the document.
struct Tok { b: Vec<u8>, idx: i64 } // idx: array index, -1 not an RFC 6901 index, i64::MAX too large
fn parse_ptr(ptr: &[u8]) -> Vec<Tok> {
    if ptr.is_empty() { return Vec::new(); }
    if ptr[0] != b'/' { fail("plain JSON pointer required"); }
    if ptr.windows(2).any(|w| w[0] == b'~' && w[1] != b'0' && w[1] != b'1') || ptr[ptr.len() - 1] == b'~' { fail("invalid pointer escape"); }
    ptr[1..].split(|&c| c == b'/').map(|raw| {
        let mut b = Vec::with_capacity(raw.len());
        let mut i = 0;
        while i < raw.len() { if raw[i] == b'~' { i += 1; b.push(if raw[i] == b'0' { b'~' } else { b'/' }); } else { b.push(raw[i]); } i += 1; }
        let idx = if b.is_empty() || (b.len() > 1 && b[0] == b'0') || !b.iter().all(u8::is_ascii_digit) { -1 }
            else if b.len() > 18 { i64::MAX } else { b.iter().fold(0i64, |a, &c| a * 10 + (c - b'0') as i64) };
        Tok { b, idx }
    }).collect()
}
struct Ctx<'a> { d: &'a [u8], toks: Vec<Vec<Tok>>, spans: Vec<(usize, usize)> }
impl<'a> Ctx<'a> {
    fn value(&mut self, p: usize, depth: usize, cur: &[(usize, usize)]) -> usize {
        if depth > MAXD { fail("too deep"); }
        let d = self.d;
        let s = ws(d, p);
        let mut p = s;
        let (mut sub, mut done) = (Vec::new(), Vec::new());
        for &(pi, k) in cur { if k == self.toks[pi].len() { done.push(pi) } else { sub.push((pi, k)) } }
        let e = match d[p] {
            b'{' => {
                let mut cnt = vec![0u32; sub.len()];
                p = ws(d, p + 1);
                let e = if d[p] == b'}' { p + 1 } else {
                    loop {
                        p = ws(d, p);
                        if d[p] != b'"' { fail("invalid object"); }
                        let ks = p + 1;
                        p = vstring(d, ks);
                        let ke = p - 1;
                        p = ws(d, p);
                        if d[p] != b':' { fail("invalid object"); }
                        let mut child = Vec::new();
                        if !sub.is_empty() {
                            let mut dec = Vec::new();
                            let key: &[u8] = if d[ks..ke].contains(&b'\\') { decode(d, ks, ke, &mut dec, false); &dec } else { &d[ks..ke] };
                            for (j, &(pi, k)) in sub.iter().enumerate() { if self.toks[pi][k].b == key { cnt[j] += 1; child.push((pi, k + 1)); } }
                        }
                        p = ws(d, self.value(p + 1, depth + 1, &child));
                        match d[p] { b',' => p += 1, b'}' => break p + 1, _ => fail("invalid object") }
                    }
                };
                if cnt.iter().any(|&c| c != 1) { fail("JSON pointer member missing or ambiguous"); }
                e
            }
            b'[' => {
                if sub.iter().any(|&(pi, k)| self.toks[pi][k].idx < 0) { fail("invalid array index"); }
                p = ws(d, p + 1);
                let mut count = 0i64;
                let e = if d[p] == b']' { p + 1 } else {
                    loop {
                        let child: Vec<_> = sub.iter().filter(|&&(pi, k)| self.toks[pi][k].idx == count).map(|&(pi, k)| (pi, k + 1)).collect();
                        p = ws(d, self.value(p, depth + 1, &child));
                        count += 1;
                        match d[p] { b',' => p += 1, b']' => break p + 1, _ => fail("invalid array") }
                    }
                };
                if sub.iter().any(|&(pi, k)| self.toks[pi][k].idx >= count) { fail("array index outside the document"); }
                e
            }
            c => {
                let e = match c {
                    b'"' => vstring(d, p + 1),
                    b't' => lit(d, p, b"true"),
                    b'f' => lit(d, p, b"false"),
                    b'n' => lit(d, p, b"null"),
                    _ => vnumber(d, p),
                };
                if !sub.is_empty() { fail("JSON pointer target is missing"); }
                e
            }
        };
        for pi in done { self.spans[pi] = (s, e); }
        e
    }
}
fn main() {
    let a: Vec<String> = env::args().collect();
    if a.len() < 4 { fail("usage: json_query extract|batch INPUT OUTPUT [POINTER ...]"); }
    let batch = a[1] == "batch";
    if !batch && (a[1] != "extract" || a.len() != 5) { fail("invalid JSON query options"); }
    let toks: Vec<Vec<Tok>> = a[4..].iter().map(|p| parse_ptr(p.as_bytes())).collect();
    let mut f = fs::File::open(&a[2]).unwrap_or_else(|_| fail("JSON query file error"));
    let mut d = Vec::with_capacity(f.metadata().map_or(0, |m| m.len() as usize) + 2 * PAD);
    if f.read_to_end(&mut d).is_err() { fail("JSON query file error"); }
    let n = d.len();
    d.resize(n + PAD, 0);
    let mut ctx = Ctx { d: &d, spans: vec![(usize::MAX, 0); toks.len()], toks };
    let init: Vec<(usize, usize)> = (0..ctx.toks.len()).map(|i| (i, 0)).collect();
    if ws(&d, ctx.value(0, 0, &init)) != n { fail("invalid JSON document"); }
    let mut o = Vec::new();
    if batch { o.push(b'['); }
    for (i, &(start, _)) in ctx.spans.iter().enumerate() {
        if i > 0 { o.push(b','); }
        if start == usize::MAX { fail("JSON pointer target is missing"); }
        rval(&d, start, &mut o);
    }
    if batch { o.push(b']'); }
    o.push(b'\n');
    if fs::write(&a[3], &o).is_err() { fail("JSON query file error"); }
}
'''

# ---- Independent Python oracle (strict JSON, exact number text, member order and duplicates preserved) ----
class Number(str):
    pass

class Members(list):
    pass

def _reject_constant(value):
    raise ValueError('invalid JSON literal: '+value)

def document(data):
    value=json.loads(data.decode('utf8'),parse_int=Number,parse_float=Number,object_pairs_hook=Members,parse_constant=_reject_constant)
    stack=[value]
    while stack:
        node=stack.pop()
        if type(node) is str:
            if any(0xd800<=ord(c)<=0xdfff for c in node):raise ValueError('lone surrogate')
        elif isinstance(node,Members):
            for key,child in node:stack.extend((key,child))
        elif isinstance(node,list):stack.extend(node)
    return value

def render(node):
    if isinstance(node,Number):return str(node)
    if isinstance(node,Members):
        return '{'+','.join(json.dumps(k,ensure_ascii=False)+':'+render(v) for k,v in node)+'}'
    if isinstance(node,list):return '['+','.join(map(render,node))+']'
    return json.dumps(node,ensure_ascii=False,separators=(',',':'))

def selected(node,pointer):
    if pointer=='':return node
    if not pointer.startswith('/'):raise ValueError('plain JSON pointer required')
    tokens=pointer[1:].split('/')
    if any(re.search(r'~(?:[^01]|$)',t) for t in tokens):raise ValueError('invalid pointer escape')
    for token in tokens:
        token=token.replace('~1','/').replace('~0','~')
        if isinstance(node,Members):
            matches=[v for k,v in node if k==token]
            if len(matches)!=1:raise KeyError(token)
            node=matches[0]
        elif isinstance(node,list):
            if not re.fullmatch(r'0|[1-9][0-9]*',token):raise ValueError('invalid array index')
            if int(token)>=len(node):raise KeyError(token)
            node=node[int(token)]
        else:raise KeyError(token)
    return node

def expected(data,mode,pointers):
    root=document(data)
    items=[render(selected(root,p)) for p in pointers]
    if mode=='extract':
        if len(items)!=1:raise ValueError('extract needs one pointer')
        return (items[0]+'\n').encode('utf8')
    return ('['+','.join(items)+']\n').encode('utf8')

# ---- controls ----
def controls(work):
    work=Path(work);cases=[];counter=[0]
    def source(data):
        counter[0]+=1;path=work/('in%d.json'%counter[0]);path.write_bytes(data);return str(path)
    def ok(name,data,pointers,mode='extract'):
        cases.append(dict(name=name,args=[mode,source(data),'{out}',*pointers],expect_exit=0,expected_file=expected(data,mode,pointers)))
    def bad(name,data,pointers=('',),mode='extract'):
        cases.append(dict(name=name,args=[mode,source(data),'{out}',*pointers],expect_exit='nonzero',stdout_empty=True))
    nested=('{"a/b":{"~":{"": [null,true,-0.00e+02,"日本語😀\\u0000",[],{}]}},'
            '"dup":1,"dup":2,"map":{"a":"first","b":"😀\\u0000","a":"last"}}').encode('utf8')
    for pointer in ('','/a~1b/~0/','/a~1b/~0//0','/a~1b/~0//2','/a~1b/~0//3','/a~1b/~0//4','/a~1b/~0//5','/map','/map/b','/a~1b'):
        ok('nested'+pointer.replace('/','_'),nested,[pointer])
    ok('batch_mixed',nested,['/a~1b/~0//2','/map/b','','/a~1b/~0//2','/a~1b/~0//5'],'batch')
    ok('batch_empty',nested,[],'batch')
    for i,text in enumerate((b'null',b'true',b'false',b'[]',b'{}',b'""',b'"\\u0000\\n\\\\\\\""',b'-0',b'123.4500E-07',b'1E400',b'0.0',
                              ('9'*10000+'e+999999').encode(),b' \t\r\n[ 1 ,\r\n\t2 , { "k" : [ ] } ]\n\n ',
                              b'"\\b\\f\\n\\r\\t\\/\\u001f\\u007f\\u00e9\\u2028\\ud83d\\ude00\\uD83D\\uDE00\\"\\\\"',
                              '" \u007f\u0085 \U0010ffff ߿ ࠀ ퟿  ￿"'.encode('utf8'),
                              b'{"a\\u0062":1,"\\ud83d\\ude00":2,"x\\/y":3,"q\\"":4}')):
        ok('value%d'%i,text,[''])
    ok('escaped_key_lookup',b'{"a\\u0062":1,"\\ud83d\\ude00":[2,3],"x\\/y":3}',['/ab','/\U0001f600/1','/x~1y'],'batch')
    ok('dup_off_path',b'{"dup":1,"dup":2,"ok":{"v":[1,{"dup":[],"dup":{}}]}}',['/ok/v/0','/ok/v/1'],'batch')
    ok('index_boundary',b'[10,20,30]',['/0','/2'],'batch')
    ok('pointer_empty_key',b'{"":{"":7}}',['/','//'],'batch')
    big_key,big_value='😀'*65537,'日本語'*65537
    big=json.dumps({big_key:big_value},ensure_ascii=False).encode()
    ok('long_key_value',big,[''])
    ok('long_key_lookup',json.dumps({'😀'*20000:'日本語'*20000},ensure_ascii=False).encode(),['/'+'😀'*20000])
    huge=json.dumps({'blob':'😀'*300000,'target':['ok']},ensure_ascii=False).encode()
    ok('huge_then_target',huge,['/target'])
    for count in (8192,8193):
        arr=('['+','.join(str(i) for i in range(count-1))+']').encode()
        ok('array%d'%count,arr,['','/'+str(count-2)],'batch')
    ok('non_ascii_pointer','{"日本語":{"é":[1]}}'.encode('utf8'),['/日本語/é/0'])
    base=b'{"a":[0],"dup":1,"dup":2,"map":{"a":1}}'
    bad('missing_key',base,['/missing'])
    bad('missing_nested',base,['/map/b'])
    bad('index_out_of_range',base,['/a/1'])
    bad('index_huge',base,['/a/'+'9'*10000])
    bad('index_dash',base,['/a/-'])
    bad('index_leading_zero',base,['/a/00'])
    bad('index_fullwidth',base,['/a/１'])
    bad('index_on_empty_array',b'[]',['/0'])
    bad('step_into_scalar',base,['/a/0/x'])
    bad('ambiguous_member',base,['/dup'])
    bad('pointer_no_slash',base,['a'])
    bad('pointer_bad_escape',base,['/a/~2'])
    bad('pointer_trailing_tilde',base,['/a/~'])
    bad('pointer_escape_late',base,['/map/a','/a/~'],'batch')
    bad('batch_late_missing',base,['/a/0','/missing'],'batch')
    bad('batch_late_index',base,['/a/0','/a/5'],'batch')
    for i,text in enumerate((b'',b' \n',b'[] trailing',b'[]]',b'NaN',b'-Infinity',b'Infinity',b'{"x":}',b'{"x":1,}',b'[1,]',b'[,1]',b'[1 2]',b'{"a" 1}',
                             b"{'a':1}",b'{a:1}',b'01',b'1.',b'.5',b'+1',b'1e',b'1e+',b'-',b'0x10',b'tru',b'nulll',b'True',b'"abc',b'"a\nb"',b'"a\tb"',b'"a\x00b"',
                             b'"\\x41"',b'"\\u12"',b'"\\u12G4"',b'"\\ud800"',b'"\\ud800\\u0041"',b'"\\udc00"',b'"\\ud83d\\ud83d"',b'"\\ude00\\ud83d"',b'"\\',
                             b'\xef\xbb\xbf[]',b'[1]\x00',b'/* c */ []',b'[1] // c',b'{"a":1 "b":2}',b'{"a":1:2}',b'{1:2}',b'[' ,b'{',b'{"a"',b'{"a":',b'[1,')):
        bad('invalid_json%d'%i,text)
    for i,text in enumerate((b'\xff',b'"\xff"',b'"\xc0\x80"',b'"\xc1\xbf"',b'"\xe0\x80\x80"',b'"\xed\xa0\x80"',b'"\xed\xbf\xbf"',b'"\xf0\x80\x80\x80"',
                             b'"\xf4\x90\x80\x80"',b'"\xf5\x80\x80\x80"',b'"\xc3"',b'"\xe3\x81"',b'"\xf0\x9f\x98"',b'"\x80"',b'"\xc3\x28"',b'"\xe3\x81\x28"',
                             b'{"target":0,"late":"\xff"}',b'{"\xff":1}',b'{"target":0} \xff',b'["a",\n"b\xe3\x81"]',b'\x80',b'[1,2]\xc3')):
        bad('invalid_utf8_%d'%i,text,['/target'] if i==16 else [''])
    deep=b'[0,'*200+b'bad'
    bad('invalid_deep',deep)
    bad('invalid_late_comma',b'{"target":0,"late":[1,]}',['/target'])
    present=source(b'{"a":[0]}')
    out='{out}'
    for name,args in (('no_args',[]),('mode_only',['extract']),('missing_pointer',['extract',present,out]),('extract_two',['extract',present,out,'','']),
                      ('extract_none_batch_arg',['extract',present]),('unknown_mode',['unknown',present,out,'']),('missing_input',['extract',str(work/'absent.json'),out,'']),('input_is_directory',['extract',str(work),out,''])):
        cases.append(dict(name='args_'+name,args=args,expect_exit='nonzero',stdout_empty=True))
    return cases

# ---- workload ----
WORDS=['alpha','beta','gamma','delta','epsilon','zeta','eta','theta','iota','kappa','lambda','sigma']
POOL=['plain ascii text','日本語のテキスト','Ünïcödé façade naïve','😀 emoji 🚀 mix','quote " and \\ backslash','tab\there\nnewline\r\n','ctl \x01\x1f end',
      'slash / and   sep','','é','Привет, мир','mixed 日本 and ascii and 😀']
NUMS=['0','-0','1','-17','3.14159','2.5e3','1E-7','-0.0','12345678901234567890','1.50E+3','0.000001','9007199254740993','123.4500E-07']

def _text(r):
    s=r.choice(POOL)+' '+r.choice(WORDS)+str(r.randrange(10**6))
    return json.dumps(s,ensure_ascii=r.random()<0.25)

def _number(r):
    if r.random()<0.4:return r.choice(NUMS)
    return '%d.%0*de%+d'%(r.randrange(-10**6,10**6),r.randrange(1,6),r.randrange(10**5),r.randrange(-30,30)) if r.random()<0.5 else str(r.randrange(-10**12,10**12))

def _obj(pairs,sep):
    return '{'+sep[0].join(json.dumps(k)+sep[1]+v for k,v in pairs)+'}'

def _record(i,r):
    x=r.random();sep=(',',':') if x<0.8 else (', ',': ') if x<0.92 else (',\n    ',' : ')
    tags='['+sep[0].join(_text(r) for _ in range(r.randrange(0,5)))+']'
    nums='['+sep[0].join(_number(r) for _ in range(r.randrange(0,6)))+']'
    pairs=[('k',_text(r)),('on',r.choice(('true','false','null')))]
    if i%97==7:pairs+=[('dup','1'),('dup','{"x":[]}')]
    nested=_obj([('a',nums),('b',_obj(pairs,sep)),('id',str(i))],sep)
    rec=_obj([('id',str(i)),('name',_text(r)),('score',_number(r)),('tags',tags),('text',_text(r)),('nested',nested)],sep)
    return rec

def generate(work,smoke):
    records=1100 if smoke else RECORDS
    r=random.Random(835);parts=[]
    for i in range(records):
        rec=_record(i,r)
        parts.append(rec)
    summary=_obj([('count',str(records)),('label',json.dumps('終端 summary 😀 "end"\n',ensure_ascii=False)),
                  ('histogram','['+','.join(str(r.randrange(10**6)) for _ in range(256))+']'),
                  ('notes',_obj([('first',_text(r)),('last',_text(r))],(',',':')))],(',',':'))
    data=('{"meta":{"version":"1.0","generator":"r835","title":"日本語 benchmark"},"records":[\n'+',\n'.join(parts)+'\n],"tail":{"summary":'+summary+
          ',"checksums":["'+'","'.join('%08x'%r.randrange(1<<32) for _ in range(8))+'"]}}\n').encode('utf8')
    path=Path(work)/'large.json';path.write_bytes(data)
    pointers=['/records/%d/tags'%(records-1),'/records/%d/nested/b'%(records//2),'/tail/summary']
    return dict(name='batch_%dB'%len(data),args=['batch',str(path),'{out}',*pointers],expect_exit=0,
                expected_file=expected(data,'batch',pointers))

RECORDS=4000  # ~1.3 MB: keeps the C reference >=4 ms/run so 16-run window sums clear the 50 ms gate

# Pure-AIL driver of the hot path for tools/profile.py (the real app links a C object):
# read, strict UTF-8 decode, one validating pass that records the pointer targets, render those.
PROFILE_SOURCE = r"""
use json_pointer_scan;

fn main() -> int {
    let text = read_bytes(sys.argv[1]).decode("utf-8");
    write_stdout_bytes((json_pointer_batch_text(text, sys.argv[2:]) + "\n").encode("utf-8"));
    return 0;
}
"""

def profile_args(case):
    mode, path, _out, *pointers = case["args"]
    return [path, *pointers], case["expected_file"]
