"""Black-box boundaries for the owned-process Linux PC sampler."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
PROGRAM = r'''#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv) {
 if(argc>1 && !strcmp(argv[1],"fill")) {for(int i=0;i<65537;i++)raise(SIGPROF);}
 else {volatile uint64_t value=1;for(uint64_t i=0;i<30000000;i++)value=value*33+i;}
 puts("ok");return 0;
}'''
LAUNCHER = r'''#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
int main(int argc,char **argv) {
 if(argc!=3)return 2;
 if(signal(SIGPROF,SIG_IGN)==SIG_ERR || setenv("AIL_PC_SAMPLE_OUT",argv[2],1))return 3;
 execl(argv[1],argv[1],(char *)0);return 4;
}'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('fresh output required')
    source=HERE/'row_cpu_sampler.c';before=hashlib.sha256(source.read_bytes()).hexdigest()
    report=dict(status='FAILED',source_sha256=before,cases=[])
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    with tempfile.TemporaryDirectory(prefix='ail-pc-probe-') as directory:
        root=Path(directory);library=root/'sampler.so';program=root/'program';launcher=root/'launcher'
        for name,content in [('program',PROGRAM),('launcher',LAUNCHER)]:
            (root/(name+'.c')).write_text(content)
        for command in [['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(source),'-o',str(library)],
                        ['gcc','-O2',str(root/'program.c'),'-o',str(program)],
                        ['gcc','-O2',str(root/'launcher.c'),'-o',str(launcher)]]:
            subprocess.run(command,capture_output=True,check=True,timeout=180)
        code=subprocess.run(['objdump','-d','--disassemble=sample_pc',str(library)],capture_output=True,check=True).stdout.decode()
        if '\tcall' in code:raise ValueError('signal handler has an out-of-line call')
        import os
        env=dict(os.environ,LD_PRELOAD=str(library));env.pop('AIL_PC_SAMPLE_OUT',None)
        for case in ('absent','active','full','report_exists','maps_exists','ignored_handler'):
            output=root/case
            if case=='report_exists':output.write_bytes(b'sentinel')
            if case=='maps_exists':Path(str(output)+'.maps').write_bytes(b'sentinel')
            configured=dict(env)
            if case not in ('absent','ignored_handler'):configured['AIL_PC_SAMPLE_OUT']=str(output)
            command=[str(launcher),str(program),str(output)] if case=='ignored_handler' else [str(program)]+(['fill'] if case=='full' else [])
            result=subprocess.run(command,env=configured,capture_output=True,timeout=30)
            record=dict(case=case,returncode=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode())
            if case=='absent':passed=result.returncode==0 and result.stdout==b'ok\n' and not result.stderr and not output.exists()
            elif case in ('active','full'):
                lines=output.read_text().splitlines();header=json.loads(lines[0]);pcs=[int(line,16) for line in lines[1:]]
                record['header']=header
                passed=result.returncode==0 and result.stdout==b'ok\n' and not result.stderr and header['count']==len(pcs) and all(0<pc<2**64 for pc in pcs)
                passed=passed and (header['status']=='ok' and header['count']>0 and header['dropped']==0 if case=='active' else header['status']=='buffer_full' and header['count']==65536 and header['dropped']>0)
                passed=passed and Path(str(output)+'.maps').stat().st_size>0
            else:
                passed=result.returncode==-signal.SIGABRT and result.stdout==b'' and b'setup_failed' in result.stderr
                if case=='report_exists':passed=passed and output.read_bytes()==b'sentinel'
                if case=='maps_exists':passed=passed and Path(str(output)+'.maps').read_bytes()==b'sentinel' and json.loads(output.read_text())['status']=='setup_failed'
                if case=='ignored_handler':passed=passed and not output.exists()
            record['passed']=passed;report['cases'].append(record)
        report['source_unchanged']=hashlib.sha256(source.read_bytes()).hexdigest()==before
        report['handler_out_of_line_calls']=False
        report['status']='PASSED' if all(case['passed'] for case in report['cases']) and report['source_unchanged'] else 'FAILED'
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],cases=len(report['cases']))));return int(report['status']!='PASSED')


if __name__=='__main__':raise SystemExit(main())
