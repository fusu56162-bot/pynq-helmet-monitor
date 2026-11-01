"""Restore exact original layout; check every byte before writing. No device access."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def restore(component,output,check_only=False):
    output=Path(output).resolve()
    rows=[x for x in json.loads((ROOT/'build/payload_map.json').read_text(encoding='utf-8')) if x['component']==component]
    if not rows:raise ValueError('Unknown component')
    pending=[]
    for row in rows:
        src=(ROOT/row['packaged']).resolve();src.relative_to(ROOT)
        dst=(output/row['original']).resolve();dst.relative_to(output)
        if sha(src)!=row['sha256']:raise RuntimeError('Payload changed: '+row['packaged'])
        if dst.exists() and (not dst.is_file() or sha(dst)!=row['sha256']):
            raise RuntimeError('Existing different file preserved: '+str(dst))
        pending.append((src,dst))
    if not check_only:
        for src,dst in pending:
            if not dst.exists():
                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
            if sha(dst)!=sha(src):raise RuntimeError('Copy verification failed')
    print('PAYLOAD_PASS',component,len(rows),'files','check_only='+str(check_only))
    return len(rows)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--component',required=True,choices=['board','pl','ncnn'])
    a.add_argument('--output',required=True);a.add_argument('--check-only',action='store_true');v=a.parse_args()
    restore(v.component,v.output,v.check_only)
