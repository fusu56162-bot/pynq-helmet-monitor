"""Offline integrity, naming and immutable identity checks. No device access."""
from pathlib import Path
import ast,hashlib,json,re
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest.items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if sha(p)!=h:raise RuntimeError('FILE_CHANGED: '+name)
    payload=json.loads((ROOT/'build/payload_map.json').read_text(encoding='utf-8'))
    seen=set()
    for x in payload:
        if sha(ROOT/x['packaged'])!=x['sha256']:raise RuntimeError('PAYLOAD_CHANGED')
        key=(x['component'],x['original'])
        if key in seen:raise RuntimeError('DUPLICATE_ORIGINAL')
        seen.add(key)
    spec=json.loads((ROOT/'data/model_identity.json').read_text())
    board={x['original']:x for x in payload if x['component']=='board'}
    for n,h in spec['originals_sha256'].items():
        if board['ncnn_candidate_20261019/'+n]['sha256']!=h:raise RuntimeError('DEPENDENCY_IDENTITY_FAILED')
    for n,h in spec['model_sha256'].items():
        if board['final224_speed_v1/profiles/new/model/'+n]['sha256']!=h:raise RuntimeError('MODEL_IDENTITY_FAILED')
    count=0
    for p in ROOT.rglob('*'):
        if p.is_dir() and p.name=='__pycache__':continue
        if '__pycache__' in p.parts:continue
        if p.name not in ('README.md','SKILL.md','LICENSE','NOTICE.md') and not re.fullmatch(r'[a-z0-9_.-]+',p.name):raise RuntimeError('INVALID_NAME: '+str(p))
        if p.is_file() and p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'));count+=1
    print('RELEASE_PASS',len(manifest),'files',len(payload),'payloads',count,'Python sources; no devices accessed')
if __name__=='__main__':main()
