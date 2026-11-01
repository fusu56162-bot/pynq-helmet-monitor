"""Install only pinned offline export wheels into this package's private work directory."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
assert sys.version_info[:2]==(3,12),'Use the existing Python3.12 environment'
assert platform.system()=='Linux' and platform.machine() in ('x86_64','AMD64')
target=ROOT/'work/export_tools';target.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(target))
import importlib.metadata
versions={'pnnx':'20260526','ncnn':'1.0.20260526'}
try:ready=all(importlib.metadata.version(k)==v for k,v in versions.items())
except importlib.metadata.PackageNotFoundError:ready=False
if not ready:
    wheels=[]
    for r in json.loads((ROOT/'export_wheels/WHEELS.json').read_text(encoding='utf-8')):
        p=ROOT/'export_wheels'/r['filename']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'];wheels.append(str(p))
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--target',str(target),*wheels],check=True)
import pnnx,ncnn
assert all(importlib.metadata.version(k)==v for k,v in versions.items())
print('OFFLINE_EXPORT_TOOLS_READY_NO_TORCH_REINSTALL',flush=True)
