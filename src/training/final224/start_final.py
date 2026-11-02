"""Launch one detached Linux training run; closing the Jupyter tab does not stop it."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--resume-run');args=parser.parse_args()
assert platform.system()=='Linux','Run this on the cloud GPU'
work=ROOT/'work';work.mkdir(exist_ok=True);pidfile=work/'ACTIVE_TRAINING.json'
if pidfile.exists():
    old=json.loads(pidfile.read_text(encoding='utf-8'))
    try:os.kill(int(old['pid']),0);alive=True
    except ProcessLookupError:alive=False
    if alive:raise RuntimeError('A recorded training process is still alive; refusing duplicate: '+str(old['pid']))
subprocess.run([sys.executable,str(ROOT/'launch_final.py'),'--stage','verify'],check=True,cwd=ROOT)
command=[sys.executable,'-u',str(ROOT/'launch_final.py'),'--stage','train','--batch','32','--workers','4']
if args.resume_run:command+=['--resume-run',args.resume_run]
log=work/'final_training.log'
with log.open('ab',buffering=0) as stream:
    process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
pidfile.write_text(json.dumps(dict(pid=process.pid,command=command,log=str(log)),indent=2)+'\n',encoding='utf-8')
print('FINAL_TRAINING_STARTED_BACKGROUND_PID',process.pid,flush=True)
print('WATCH: tail -n 30 -f '+str(log),flush=True)
print('150 epochs; early stopping disabled. Ctrl+C while watching stops the watcher only.',flush=True)
