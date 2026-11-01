"""Remove in-place detection-head CopyTo/Crop using existing Slice/Concat layers.

Only graph connectivity changes: no weights, constants, precision or arithmetic.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from prepare_mixed import Runtime,PACKAGE as TRAIN_PACKAGE,module,sha,save

ROOT=Path(__file__).resolve().parent
OLD=Path('D:/Codex/handoffs/camera_mjpg_20261024_r2/camera_mjpg_v2')
SOURCE=Path('D:/Codex/handoffs/final224_board_20261026_r1/final224_model_v1')
DEST=ROOT/'copyto_compat_v2'


def rewrite(text):
    lines=text.splitlines();assert lines[0]=='7767517'
    parsed=[line.split() for line in lines[2:]]
    assert len(parsed)==int(lines[1].split()[0])
    conv_indices=[i for i,p in enumerate(parsed) if p[0]=='Convolution']
    assert len(conv_indices)==60
    begin=conv_indices[-3]
    out=parsed[:begin]
    for level,start in enumerate(conv_indices[-3:]):
        stop=conv_indices[-2+level] if level<2 else len(parsed)-1
        block=parsed[start:stop]
        assert [p[0] for p in block[:4]]==['Convolution','Reshape','Permute','Sigmoid']
        assert sum(p[0]=='CopyTo' for p in block)==2 and sum(p[0]=='Crop' for p in block)==2
        assert block[-1][0]=='Reshape'
        elt=next(p.copy() for p in block if p[0]=='Eltwise')
        eltidx=next(i for i,p in enumerate(block) if p[0]=='Eltwise')
        stride_mul=block[eltidx+1].copy()
        assert stride_mul[0]=='BinaryOp' and stride_mul[2:4]==['1','1'] and stride_mul[4]==elt[6]
        power=next(p.copy() for p in block if p[0]=='UnaryOp')
        times2=next(p.copy() for p in block if p[0]=='BinaryOp' and p[5]==power[4])
        anchor_mul=next(p.copy() for p in block if p[0]=='BinaryOp' and p[2:4]==['2','1'] and p[4]==power[5])
        assert '0=4' in power and float(dict(p.split('=') for p in times2[6:])['2'])==2.
        names=['compat_head%d_%s'%(level,kind) for kind in ('xy','wh','scores')]
        split=['Slice','compat_slice_'+str(level),'1','3',block[3][5],*names,'-23300=3,2,2,5','1=3']
        elt[4]=names[0];times2[4]=names[1]
        concat=['Concat','compat_concat_'+str(level),'3','1',stride_mul[5],anchor_mul[6],names[2],block[-1][4],'0=3']
        out.extend([*block[:4],split,elt,stride_mul,times2,power,anchor_mul,concat,block[-1]])
    out.append(parsed[-1])
    assert parsed[-1][0]=='Concat' and parsed[-1][4+int(parsed[-1][2])]=='out0'
    produced=set();layernames=set()
    for p in out:
        inputs,outputs=int(p[2]),int(p[3])
        assert p[1] not in layernames;layernames.add(p[1])
        assert all(n in produced for n in p[4:4+inputs]),p
        new=p[4+inputs:4+inputs+outputs]
        assert not produced.intersection(new),p
        produced.update(new)
    assert not any(p[0] in ('CopyTo','Crop') for p in out)
    oldtypes={s.split()[0] for s in (OLD/'model/best.ncnn.param').read_text().splitlines()[2:]}
    assert {p[0] for p in out}<=oldtypes
    return '\n'.join(['7767517',f'{len(out)} {len(produced)}',*(' '.join(p) for p in out)])+'\n'


def main():
    DEST.mkdir(exist_ok=True)
    assert not (DEST/'COMPATIBILITY_CHECK.json').exists(),'Completed conversion already exists'
    exporter=module('compat_exporter',TRAIN_PACKAGE/'export_candidate.py')
    selector=module('compat_selector',TRAIN_PACKAGE/'target_selection.py')
    runtimes={};counts={};checks={}
    for name,quant in [('model',True),('fp32_model',False)]:
        target=DEST/name;target.mkdir(exist_ok=True)
        src=SOURCE/name
        param=rewrite((src/'best.ncnn.param').read_text())
        param_path=target/'best.ncnn.param'
        if param_path.exists():assert param_path.read_text()==param
        else:param_path.write_text(param,encoding='ascii')
        if not (target/'best.ncnn.bin').exists():shutil.copy2(src/'best.ncnn.bin',target/'best.ncnn.bin')
        assert sha(src/'best.ncnn.bin')==sha(target/'best.ncnn.bin')
        runtimes[name]=(Runtime(src,quant),Runtime(target,quant));checks[name]=[]
    rows=[json.loads(s) for s in (TRAIN_PACKAGE/'DATASET_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[r for r in rows if r['group']!='train'];assert len(rows)==579
    rescore={name:[] for name in runtimes}
    for i,r in enumerate(rows):
        path=TRAIN_PACKAGE/'work/data/images'/r['group']/(r['id']+'.png')
        assert sha(path)==r['image_sha256'];x=exporter.tensor(path)
        for name,(before,after) in runtimes.items():
            a,b=before(x),after(x)
            check=exporter.parity(a,b)
            assert np.array_equal(a.view(np.uint32),b.view(np.uint32)),(name,r['id'],check)
            checks[name].append(dict(id=r['id'],byte_exact=True,**check))
            truth=[[int(c),(cx-w/2)*640,(cy-h/2)*640-80,(cx+w/2)*640,(cy+h/2)*640-80] for c,cx,cy,w,h in r['truth224']]
            rescore[name].append(dict(id=r['id'],scope=r['validation_scope'],truth=truth,
                classes=[2,3] if r['scope']=='head_only_partial' else list(range(4)),predictions=selector.decode224(b).tolist()))
        if (i+1)%150==0:print('COPYTO_COMPAT_VERIFIED',i+1,'/579',flush=True)
    result=dict(status='COPYTO_REMOVED_PC1158_PAIRS_BIT_EXACT_ARM_RECHECK_PENDING',
        images579_per_precision=True,pairs=1158,all_raw_outputs_byte_exact=True,
        all_weight_bin_files_unchanged=True,only_head_Slice_Concat_graph_rewrite=True,
        all_layer_types_subset_of_previous_outdoor_model=True,
        thresholds_precision_and_first_two_layers_unchanged=True,
        model_hashes={name:{n:sha(DEST/name/n) for n in ['best.ncnn.param','best.ncnn.bin']} for name in runtimes},
        assessments={name:selector.assess(r) for name,r in rescore.items()},checks=checks,
        actual_ARM_passed=False,FPGA_loaded=False,accuracy80_accepted=False)
    save(DEST/'COMPATIBILITY_CHECK.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','assessments')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
