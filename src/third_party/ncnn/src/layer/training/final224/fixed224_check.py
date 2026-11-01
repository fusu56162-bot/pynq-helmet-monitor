"""Fixed camera thresholds, one 224 whole frame, separate annotation scopes."""
import collections
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'evaluation_support'))
from parity_support import decode224, THRESHOLDS
from b_candidate.scoring import score

NAMES=['ebike','rider','helmet_head','bare_head']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(weights,records,dest,device):
    dest.mkdir(parents=True,exist_ok=False)
    models={};before={};anchors=None
    for tag,path in weights.items():
        before[tag]=sha(path)
        checkpoint=torch.load(path,map_location='cpu',weights_only=False)
        model=(checkpoint.get('ema') or checkpoint['model']).float().to(device).eval()
        names=list(model.names.values()) if isinstance(model.names,dict) else list(model.names)
        assert names==NAMES and model.model[-1].nc==4
        if anchors is None:anchors=model.model[-1].anchors.detach().cpu().clone()
        else:assert torch.equal(anchors,model.model[-1].anchors.detach().cpu())
        model.model[-1].export=False
        models[tag]=model
    totals=collections.defaultdict(collections.Counter)
    per_class=collections.defaultdict(collections.Counter)
    used=[r for r in records if r['group']!='train']
    assert len(used)==579
    with (dest/'PREDICTIONS.jsonl').open('x',encoding='utf-8') as stream:
        for r in used:
            p=Path(r['materialized_image']);assert sha(p)==r['image_sha256']
            im=cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
            assert im.shape==(224,224,3)
            x=torch.from_numpy(np.ascontiguousarray(im[...,::-1].transpose(2,0,1)[None])).to(device).float()/255.
            truth=[[int(c),(cx-w/2)*640,(cy-h/2)*640-80,(cx+w/2)*640,(cy+h/2)*640-80]
                   for c,cx,cy,w,h in r['truth224']]
            classes=[2,3] if r['scope']=='head_only_partial' else list(range(4))
            row=dict(id=r['id'],scope=r['validation_scope'],classes=classes,truth=truth)
            for tag,model in models.items():
                with torch.no_grad():raw=model(x)[0].float().cpu().numpy()
                assert raw.shape==(1,3087,9) and np.isfinite(raw).all()
                pred=decode224(raw)
                got=score(pred,truth,classes)
                row[tag]=dict(predictions=pred.tolist(),score=got)
                key=r['validation_scope']+'/'+tag
                totals[key].update(images=1,tp=got['tp'],fp=got['fp'],fn=got['fn'])
                totals[key]['empty_images']+=int(not truth)
                totals[key]['empty_with_predictions']+=int(not truth and bool(len(pred)))
                for c in classes:
                    part=score(pred,truth,[c])
                    per_class[key+'/'+NAMES[c]].update({k:part[k] for k in ('tp','fp','fn')})
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    metrics={}
    for key,c in per_class.items():
        metrics[key]=dict(c,precision=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None,
                          recall=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None)
    assert all(sha(path)==before[tag] for tag,path in weights.items())
    result=dict(status='FIXED224_DEVELOPMENT_VALIDATION_NOT_85_CERTIFICATION',images=579,
        model_image_pairs=len(used)*len(models),weights_sha256=before,input=[1,3,224,224],output=[1,3087,9],
        names=NAMES,thresholds=THRESHOLDS,nms_iou=.45,matching_iou=.5,per_class=metrics,
        counts={k:dict(v) for k,v in totals.items()},unfused_fp32=True,roi=False,multiscale=False,
        validation_is_development_not_blind_test=True,speed_not_measured=True,board_changed=False)
    save(dest/'SUMMARY.json',result)
    for tag in models:
        print('FIXED224_FIELD23',tag,flush=True)
        for name in NAMES:
            m=metrics['field23/'+tag+'/'+name]
            print(name,'TP/FP/FN',m['tp'],m['fp'],m['fn'],'P/R',m['precision'],m['recall'],flush=True)
    return result
