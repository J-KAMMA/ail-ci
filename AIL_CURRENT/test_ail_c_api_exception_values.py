"""Independent C caller checks owning exception messages and bounded error ABI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ail_c_objects as support

class CApiExceptionValueTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    def test_owned_messages_bounds_and_repeated_failure_recovery(self):
        source=self.write('errors.ail','fn fail(message:str)->int {raise ValueError(message);return 0;} fn success()->int {return 7;}')
        output=self.root/'library';compiled=self.command('compile-library',source,'--name','errdemo','-o',output,'--json')
        self.assertEqual(compiled.returncode,0,(compiled.stdout+compiled.stderr).decode(errors='replace'))
        self.assertEqual(json.loads(compiled.stdout)['status'],'passed')
        caller=self.write('caller.c',r'''
#include "errdemo.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv) {
    if(argc!=2) return 20;
    unsigned char data[65536],saved[65536];
    FILE *f=fopen(argv[1],"rb"); if(!f) return 21;
    size_t size=fread(data,1,sizeof data,f); if(ferror(f)||!feof(f)) return 22; fclose(f);
    memcpy(saved,data,size); errdemo_error first={0};
    for(int i=0;i<128;i++) {
        int64_t out=99; errdemo_error error; memset(&error,0xA5,sizeof error);
        errdemo_view view={size?data:NULL,size};
        int status=errdemo_fail(view,&out,&error);
        if(status!=1 || out!=99 || error.code!=1 || !memchr(error.message,0,sizeof error.message)) return 23;
        if(i==0) first=error; else if(strcmp(first.message,error.message)) return 24;
        if(memcmp(saved,data,size)) return 25;
        if(errdemo_success(&out,&error)!=0 || out!=7 || error.code!=0 || error.message[0]) return 26;
    }
    printf("1|99|1|"); fwrite(first.message,1,strlen(first.message),stdout); putchar(10); return 0;
}
''')
        compiler=os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        binary=self.root/('caller.exe' if os.name=='nt' else 'caller')
        built=subprocess.run([compiler,'-std=c11','-O2','-I',str(output),str(caller),str(output/'errdemo.o'),'-o',str(binary)],capture_output=True,timeout=180)
        self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
        # Oracle counts UTF-8 bytes, first NUL and complete scalars independently of generated C.
        cases=['','a','日本😀','before\0after','x'*158+'é','x'*157+'é','x'*159,'x'*160,'x'*158+'😀','日本😀'*4000]
        path=self.root/'input.bin'
        for text in cases:
            raw=text.encode();path.write_bytes(raw)
            message='ValueError' if not text else ''
            if text:
                for character in text:
                    if character=='\0' or len((message+character).encode())>159:break
                    message+=character
            result=subprocess.run([str(binary),str(path)],capture_output=True,timeout=30)
            self.assertEqual((result.returncode,result.stderr),(0,b''),repr(text[:32]))
            self.assertEqual(result.stdout.replace(b'\r\n',b'\n'),b'1|99|1|'+message.encode()+b'\n')
            self.assertEqual(path.read_bytes(),raw)

if __name__=='__main__':unittest.main()