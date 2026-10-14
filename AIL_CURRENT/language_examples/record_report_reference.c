#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>
#include <time.h>
#include <errno.h>
#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
#else
#include <sys/stat.h>
#endif

typedef struct { unsigned char *p; size_t n, cap; } Buffer;
typedef struct { unsigned char *key; size_t n; int64_t value; } Row;
typedef struct { Row *p; size_t n, cap; } Rows;
static void fatal(void) { exit(1); }
static void reserve(Buffer *b, size_t add) {
    size_t need, cap;
    if (add > SIZE_MAX - b->n) fatal();
    need = b->n + add;
    if (need <= b->cap) return;
    cap = b->cap ? b->cap : 4096;
    while (cap < need) { if (cap > SIZE_MAX / 2) { cap = need; break; } cap *= 2; }
    { void *p = realloc(b->p, cap); if (!p) fatal(); b->p = p; b->cap = cap; }
}
static void append(Buffer *b, const void *p, size_t n) { reserve(b,n); if(n) memcpy(b->p+b->n,p,n); b->n+=n; }
static void rr_byte(Buffer *b, unsigned char c) { append(b,&c,1); }
static void literal(Buffer *b, const char *s) { append(b,s,strlen(s)); }
static uint64_t now_ns(void) {
#ifdef _WIN32
    LARGE_INTEGER t,f; QueryPerformanceCounter(&t); QueryPerformanceFrequency(&f);
    return (uint64_t)(t.QuadPart/f.QuadPart)*1000000000ULL +
        (uint64_t)((long double)(t.QuadPart%f.QuadPart)*1000000000.0L/f.QuadPart);
#else
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) fatal();
    return (uint64_t)t.tv_sec*1000000000ULL+(uint64_t)t.tv_nsec;
#endif
}
static int utf8(const unsigned char *p,size_t n) {
    size_t i=0;
    while(i<n) {
        unsigned c=p[i++], lo=0x80, hi=0xbf, more;
        if(c<0x80) continue;
        if(c>=0xc2 && c<=0xdf) more=1;
        else if(c>=0xe0 && c<=0xef) { more=2; if(c==0xe0) lo=0xa0; if(c==0xed) hi=0x9f; }
        else if(c>=0xf0 && c<=0xf4) { more=3; if(c==0xf0) lo=0x90; if(c==0xf4) hi=0x8f; }
        else return 0;
        if(more>n-i || p[i]<lo || p[i]>hi) return 0;
        ++i; while(--more) { if(p[i]<0x80 || p[i]>0xbf) return 0; ++i; }
    } return 1;
}
static int integer(const Buffer *b,int64_t *v) {
    size_t i=0; int negative=0; uint64_t x=0,limit;
    if(i<b->n && (b->p[i]=='+' || b->p[i]=='-')) negative=b->p[i++]=='-';
    if(i==b->n) return 0;
    limit=negative ? (uint64_t)INT64_MAX+1 : (uint64_t)INT64_MAX;
    for(;i<b->n;++i) { unsigned c=b->p[i]; if(c<'0'||c>'9') return 0;
        c-='0'; if(x>(limit-c)/10) return 0; x=x*10+c; }
    *v=negative ? (x==(uint64_t)INT64_MAX+1 ? INT64_MIN : -(int64_t)x) : (int64_t)x;
    return 1;
}
static int addrow(Rows *r,Buffer *key,Buffer *value) {
    int64_t v; if(!integer(value,&v)) return 0;
    if(r->n==r->cap) {
        size_t cap=r->cap ? r->cap : 64;
        if(r->cap) { if(cap>SIZE_MAX/2) fatal(); cap*=2; }
        if(cap>SIZE_MAX/sizeof(Row)) fatal();
        { void *p=realloc(r->p,cap*sizeof(Row)); if(!p) fatal(); r->p=p; r->cap=cap; }
    }
    r->p[r->n].key=key->p; r->p[r->n].n=key->n; r->p[r->n].value=v; ++r->n;
    key->p=NULL; key->n=key->cap=0; value->n=0; return 1;
}
/* States: field start, unquoted, quoted, after closing quote. */
static int parse(const Buffer *in,Rows *rows) {
    Buffer fields[2]={{0},{0}}; size_t i=0; unsigned field=0,state=0; int started=0,ok=0;
    if(!utf8(in->p,in->n)) goto done;
    while(i<in->n) {
        unsigned char c=in->p[i++];
        if(state==2) {
            if(c=='"') { if(i<in->n && in->p[i]=='"') { ++i; rr_byte(&fields[field],c); } else state=3; }
            else rr_byte(&fields[field],c);
            continue;
        }
        if(c==',' || c=='\r' || c=='\n') {
            if(c==',') { if(field==1) goto done; field=1; state=0; started=1; continue; }
            if(c=='\r' && i<in->n && in->p[i]=='\n') ++i;
            if(started) { if(field!=1 || !addrow(rows,&fields[0],&fields[1])) goto done; }
            field=state=0; started=0; continue;
        }
        if(state==3) goto done;
        started=1;
        if(c=='"') { if(state!=0) goto done; state=2; }
        else { rr_byte(&fields[field],c); state=1; }
    }
    if(state==2) goto done;
    if(started && (field!=1 || !addrow(rows,&fields[0],&fields[1]))) goto done;
    ok=1;
done: free(fields[0].p); free(fields[1].p); return ok;
}
static int selected(int mode,int64_t v) { return mode==0 || (mode==1 ? v>0 : v!=0); }
static void number(Buffer *b,int64_t v) {
    char s[32]; int n=snprintf(s,sizeof(s),"%lld",(long long)v); if(n<0 || (size_t)n>=sizeof(s)) fatal(); append(b,s,(size_t)n);
}
static void count_number(Buffer *b,size_t v) {
    char s[3*sizeof(size_t)+1]; int n=snprintf(s,sizeof(s),"%zu",v); if(n<0 || (size_t)n>=sizeof(s)) fatal(); append(b,s,(size_t)n);
}
static void key_json(Buffer *b,const Row *r) {
    static const char hex[]="0123456789abcdef"; size_t i; rr_byte(b,'"');
    for(i=0;i<r->n;++i) { unsigned char c=r->key[i]; const char *s=NULL;
        switch(c) { case '"': s="\\\""; break; case '\\': s="\\\\"; break;
        case '\b': s="\\b"; break; case '\f': s="\\f"; break; case '\n': s="\\n"; break;
        case '\r': s="\\r"; break; case '\t': s="\\t"; break; }
        if(s) literal(b,s); else if(c<32) { char e[6]={'\\','u','0','0',hex[c>>4],hex[c&15]}; append(b,e,6); } else rr_byte(b,c);
    } rr_byte(b,'"');
}
#ifdef _WIN32
typedef wchar_t PathChar;
static FILE *open_file(const PathChar *p,int writing) { return _wfopen(p,writing ? L"wb" : L"rb"); }
static int mode_value(const PathChar *s) { return !wcscmp(s,L"all") ? 0 : !wcscmp(s,L"positive") ? 1 : !wcscmp(s,L"nonzero") ? 2 : -1; }
static int distinct_files(const PathChar *input,const PathChar *output) {
    HANDLE a,b; BY_HANDLE_FILE_INFORMATION ai,bi; DWORD error; int ok=0;
    a=CreateFileW(input,0,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(a==INVALID_HANDLE_VALUE) return 0;
    if(!GetFileInformationByHandle(a,&ai)) { CloseHandle(a); return 0; }
    b=CreateFileW(output,0,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(b==INVALID_HANDLE_VALUE) {
        error=GetLastError(); ok=error==ERROR_FILE_NOT_FOUND || error==ERROR_PATH_NOT_FOUND;
    } else {
        if(GetFileInformationByHandle(b,&bi))
            ok=ai.dwVolumeSerialNumber!=bi.dwVolumeSerialNumber || ai.nFileIndexHigh!=bi.nFileIndexHigh || ai.nFileIndexLow!=bi.nFileIndexLow;
        if(!CloseHandle(b)) ok=0;
    }
    if(!CloseHandle(a)) ok=0;
    return ok;
}
int wmain(int argc,wchar_t **argv) {
#else
typedef char PathChar;
static FILE *open_file(const PathChar *p,int writing) { return fopen(p,writing ? "wb" : "rb"); }
static int mode_value(const PathChar *s) { return !strcmp(s,"all") ? 0 : !strcmp(s,"positive") ? 1 : !strcmp(s,"nonzero") ? 2 : -1; }
static int distinct_files(const PathChar *input,const PathChar *output) {
    struct stat a,b;
    if(stat(input,&a)) return 0;
    if(stat(output,&b)) return errno==ENOENT;
    return a.st_dev!=b.st_dev || a.st_ino!=b.st_ino;
}
int main(int argc,char **argv) {
#endif
    Buffer input={0},output={0}; Rows rows={0}; FILE *f=NULL; int status=3,mode; size_t i,count=0; int64_t total=0;
    uint64_t start=now_ns(),t=start,read_ns=0,parse_ns=0,select_ns=0,render_ns=0,write_ns=0;
    if(argc!=4) { status=2; goto done; }
    mode=mode_value(argv[3]); if(mode<0) { status=4; goto done; }
    if(!distinct_files(argv[1],argv[2])) goto done;
    f=open_file(argv[1],0); if(!f) goto done;
    t=now_ns();
    for(;;) { size_t n; reserve(&input,65536); n=fread(input.p+input.n,1,65536,f); input.n+=n;
        if(n<65536) { if(ferror(f)) goto done; break; } }
    { int e=fclose(f); f=NULL; if(e) goto done; }
    read_ns=now_ns()-t; t=now_ns();
    if(!parse(&input,&rows)) { status=4; goto done; }
    parse_ns=now_ns()-t; t=now_ns();
    for(i=0;i<rows.n;++i) if(selected(mode,rows.p[i].value)) {
        int64_t v=rows.p[i].value;
        if((v>0 && total>INT64_MAX-v) || (v<0 && total<INT64_MIN-v)) { status=4; goto done; }
        total+=v; if(count==SIZE_MAX) fatal(); ++count;
    }
    select_ns=now_ns()-t; t=now_ns(); literal(&output,"{\"rows\":[");
    { int first=1; for(i=0;i<rows.n;++i) if(selected(mode,rows.p[i].value)) {
        if(!first) rr_byte(&output,',');
        first=0; literal(&output,"{\"key\":"); key_json(&output,&rows.p[i]);
        literal(&output,",\"value\":"); number(&output,rows.p[i].value); rr_byte(&output,'}');
    } }
    literal(&output,"],\"count\":"); count_number(&output,count); literal(&output,",\"total\":"); number(&output,total); rr_byte(&output,'}');
    render_ns=now_ns()-t; t=now_ns();
    f=open_file(argv[2],1); if(!f) goto done;
    if(fwrite(output.p,1,output.n,f)!=output.n) goto done;
    { int e=fclose(f); f=NULL; if(e) goto done; }
    write_ns=now_ns()-t; status=0;
done:
    if(f) fclose(f);
#ifdef RECORD_REPORT_PROFILE
    fprintf(stderr,"PROFILE {\"read_ns\":%llu,\"parse_ns\":%llu,\"select_ns\":%llu,\"render_ns\":%llu,\"write_ns\":%llu,\"total_ns\":%llu,\"input_bytes\":%zu,\"output_bytes\":%zu}\n",
        (unsigned long long)read_ns,(unsigned long long)parse_ns,(unsigned long long)select_ns,(unsigned long long)render_ns,(unsigned long long)write_ns,(unsigned long long)(now_ns()-start),input.n,output.n);
#else
    (void)start; (void)read_ns; (void)parse_ns; (void)select_ns; (void)render_ns; (void)write_ns;
#endif
    for(i=0;i<rows.n;++i) free(rows.p[i].key);
    free(rows.p); free(input.p); free(output.p); return status;
}
