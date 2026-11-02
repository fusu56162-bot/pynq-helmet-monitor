"""Prepare trained final224 mixed candidates, without altering the old deployment."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import cv2
import ncnn
import numpy as np

ROOT = Path(__file__).resolve().parent
TRAINING = ROOT.parent/'joint_model_training_v1'
SOURCE = TRAINING/'final_result_20261025/received/run/MODEL_EXPORT'
PACKAGE = Path('D:/Codex/handoffs/joint_final224_20261025_r1/joint_final224')
TOOLS = Path('D:/Codex/tmp/ncnn_tools_20260526/ncnn-20260526-windows-vs2022/x64/bin')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


class Runtime:
    def __init__(self,folder,int8=False):
        self.net=ncnn.Net();o=self.net.opt;o.num_threads=2;o.use_vulkan_compute=False
        o.use_fp16_packed=o.use_fp16_storage=o.use_fp16_arithmetic=False;o.use_bf16_storage=False
        o.use_int8_inference=int8
        if not int8:o.use_packing_layout=False
        assert self.net.load_param(str(folder/'best.ncnn.param'))==0
        assert self.net.load_model(str(folder/'best.ncnn.bin'))==0
    def __call__(self,x):
        e=self.net.create_extractor();assert e.input('in0',ncnn.Mat(x[0]).clone())==0
        code,out=e.extract('out0');assert code==0
        a=np.array(out,dtype=np.float32).reshape(1,3087,9).copy()
        assert np.isfinite(a).all();return a


def main():
    cv2.setNumThreads(1)
    pins=json.loads((SOURCE/'MODEL_INTERFACE.json').read_text())
    assert sha(SOURCE/'best.ncnn.param')==pins['ncnn_param_sha256']
    assert sha(SOURCE/'best.ncnn.bin')==pins['ncnn_bin_sha256']
    exporter=module('verified_final_export',PACKAGE/'export_candidate.py')
    selector=module('verified_final_selector',PACKAGE/'target_selection.py')
    dest=ROOT/'models';dest.mkdir(exist_ok=False)
    fp32=dest/'fp32_reorg';fp32.mkdir()
    lines=(SOURCE/'best.ncnn.param').read_text().splitlines()
    layers,blobs=map(int,lines[1].split());convs=[];swish=[]
    for i in range(2,len(lines)):
        s=lines[i].split()
        if s[0]=='Convolution':convs.append((i,s))
        elif s[0]=='Swish':swish.append((i,s))
    assert len(convs)==60
    for j,(i,s) in enumerate(convs):s[1]='conv_'+str(j);lines[i]=' '.join(s)
    for j,(i,s) in enumerate(swish):
        s[1]=['silu_75','silu_76'][j] if j<2 else 'final_activation_'+str(j)
        lines[i]=' '.join(s)
    index=convs[0][0];s=lines[index].split()
    assert s[:6]==['Convolution','conv_0','1','1','in0','1']
    p=dict(v.split('=') for v in s[6:]);assert p['1']=='6' and p['3']=='2' and p['4']=='2'
    s[4]='stem_reorg_blob';changes={'1':'3','11':'3','3':'1','13':'1','4':'1','14':'1'}
    s[6:]=[k+'='+changes.get(k,v) for k,v in p.items()]
    lines[index]=' '.join(s);lines.insert(index,'Reorg stem_reorg 1 1 in0 stem_reorg_blob 0=2 1=0')
    lines[1]=f'{layers+1} {blobs+1}'
    binary=(SOURCE/'best.ncnn.bin').read_bytes();assert struct.unpack_from('<I',binary)[0]==0
    old=np.frombuffer(binary,'<f4',1728,4).reshape(16,3,6,6)
    new=old.reshape(16,3,3,2,3,2).transpose(0,1,3,5,2,4).reshape(16,12,3,3)
    inverse=new.reshape(16,3,2,2,3,3).transpose(0,1,4,2,5,3).reshape(old.shape)
    assert inverse.tobytes()==old.tobytes()
    end=4+1728*4
    changed=binary[:4]+new.tobytes()+binary[end:]
    assert changed[end:]==binary[end:]
    (fp32/'best.ncnn.param').write_text('\n'.join(lines)+'\n',encoding='ascii')
    (fp32/'best.ncnn.bin').write_bytes(changed)
    original=Runtime(SOURCE);reorg=Runtime(fp32)
    samples=json.loads((PACKAGE/'EXPORT_SAMPLES.json').read_text())
    records=[json.loads(s) for s in (PACKAGE/'DATASET_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
    byid={r['id']:r for r in records}
    checks=[]
    for name in samples['probe_ids']:
        r=byid[name];path=PACKAGE/'work/data/images'/r['group']/(name+'.png')
        assert sha(path)==r['image_sha256'];x=exporter.tensor(path)
        checks.append(dict(id=name,**exporter.parity(original(x),reorg(x))))
    save(ROOT/'REORG_CHECK.json',dict(status='WEIGHT_PERMUTATION_AND12_MODEL_PARITY_PASS',
        exact_weight_inverse=True,binary_suffix_unchanged=True,checks=checks))
    print('TRAINED_MODEL_REORG12_PARITY_PASS',flush=True)
    calibration=ROOT/'calibration';calibration.mkdir()
    listing=[];rows=[]
    for index,name in enumerate(samples['calibration_ids']):
        r=byid[name];assert r['group']=='train'
        path=PACKAGE/'work/data/images/train'/(name+'.png');assert sha(path)==r['image_sha256']
        target=calibration/('%03d.npy'%index);np.save(target,exporter.tensor(path)[0],allow_pickle=False)
        listing.append(str(target));rows.append(dict(id=name,source_sha256=sha(path),tensor_sha256=sha(target)))
    (calibration/'filelist.txt').write_text('\n'.join(listing)+'\n',encoding='ascii')
    save(calibration/'MANIFEST.json',rows)
    table=calibration/'calibration.table'
    command=[str(TOOLS/'ncnn2table.exe'),str(fp32/'best.ncnn.param'),str(fp32/'best.ncnn.bin'),
        str(calibration/'filelist.txt'),str(table),'shape=[224,224,3]','thread=2','method=kl','type=1']
    with (calibration/'conversion.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    assert table.exists();print('TRAINING_ONLY128_CALIBRATION_DONE',flush=True)
    variants=[('mixed_recover5',{6,11,57,58,59}),('prefix_int8_suffix_fp32',set(range(2,60)))]
    plans={}
    for name,fp_indices in variants:
        folder=dest/name;folder.mkdir()
        skip={'conv_'+str(i) for i in fp_indices}
        selected=folder/'mixed.table'
        selected.write_text('\n'.join(s for s in table.read_text().splitlines()
            if s.split()[0].split('_param_')[0] not in skip)+'\n',encoding='ascii')
        cmd=[str(TOOLS/'ncnn2int8.exe'),str(fp32/'best.ncnn.param'),str(fp32/'best.ncnn.bin'),
            str(folder/'best.ncnn.param'),str(folder/'best.ncnn.bin'),str(selected)]
        with (folder/'convert.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        actual=[]
        for s in (folder/'best.ncnn.param').read_text().splitlines()[2:]:
            t=s.split()
            if t[0]=='Convolution' and not any(v.startswith('8=') and v!='8=0' for v in t):actual.append(t[1])
        assert set(actual)==skip
        raw=(folder/'best.ncnn.bin').read_bytes()
        assert struct.unpack_from('<I',raw)[0]==0xd4b38 and struct.unpack_from('<I',raw,1864)[0]==0xd4b38
        plans[name]=dict(fp32_convolution_indices=sorted(fp_indices),quantized_convolution_count=60-len(fp_indices),
            model_sha256={n:sha(folder/n) for n in ['best.ncnn.param','best.ncnn.bin']})
    # Assess exactly these two predetermined precision plans; keep thresholds fixed.
    evaluations={};per_image=[]
    for name,_ in variants:
        runtime=Runtime(dest/name,True);rows=[]
        for r in records:
            if r['group']=='train':continue
            path=PACKAGE/'work/data/images'/r['group']/(r['id']+'.png')
            assert sha(path)==r['image_sha256']
            pred=selector.decode224(runtime(exporter.tensor(path)))
            truth=[[int(c),(x-w/2)*640,(y-h/2)*640-80,(x+w/2)*640,(y+h/2)*640-80] for c,x,y,w,h in r['truth224']]
            row=dict(id=r['id'],scope=r['validation_scope'],classes=[2,3] if r['scope']=='head_only_partial' else list(range(4)),
                truth=truth,predictions=pred.tolist())
            rows.append(row);per_image.append(dict(variant=name,**row))
        evaluations[name]=selector.assess(rows)
        print('MIXED_CHECK',name,json.dumps({k:v for k,v in evaluations[name]['per_class'].items() if k.startswith('field23/')},ensure_ascii=False),flush=True)
    # Prefer the existing recover5 precision layout only if it retains the FP32
    # campus TPs; otherwise retain the prefix-only quantized candidate for review.
    selected='mixed_recover5'
    if any(evaluations[selected]['per_class']['field23/'+c]['tp']<v for c,v in [('ebike',9),('rider',8),('bare_head',3)]):
        selected='prefix_int8_suffix_fp32'
    save(ROOT/'MIXED_SELECTION.json',dict(status='LOCAL_MIXED_CANDIDATES_CHECKED_NOT_ARM_OR_FPGA_ACCEPTED',
        selected=selected,source_checkpoint_sha256=pins['source_checkpoint_sha256'],plans=plans,evaluations=evaluations,
        selection_on_reused_development_not_blind_accuracy=True,calibration_only_training128=True,
        old_models_unchanged=True,FPGA_not_built=True,board_not_modified=True))
    with (ROOT/'MIXED_PREDICTIONS.jsonl').open('x',encoding='utf-8') as f:
        for r in per_image:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('MIXED_READY',selected,flush=True)


if __name__=='__main__':main()
