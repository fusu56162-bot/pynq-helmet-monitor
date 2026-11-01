"""Development-only epoch selection for campus90 and helmet85, never training on val."""
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


def state_sha(model):
    h=hashlib.sha256()
    for name,tensor in sorted(model.state_dict().items()):
        value=tensor.detach().cpu().contiguous()
        h.update(name.encode()+b'\0'+str(value.dtype).encode()+str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes())
    return h.hexdigest()


def assess(rows,tag=None):
    counts=collections.defaultdict(collections.Counter);per_class=collections.defaultdict(collections.Counter)
    for r in rows:
        pred=r[tag]['predictions'] if tag else r['predictions']
        truth=r['truth'];classes=r['classes'];scope=r['scope']
        got=score(pred,truth,classes)
        counts[scope].update(images=1,tp=got['tp'],fp=got['fp'],fn=got['fn'])
        if truth:counts[scope].update(positive_images=1,exact_positive_images=int(got['exact_given_annotation_match']))
        else:counts[scope].update(empty_images=1,empty_with_predictions=int(bool(len(pred))))
        for c in classes:
            one=score(pred,truth,[c]);per_class[scope+'/'+NAMES[c]].update({k:one[k] for k in ('tp','fp','fn')})
    metrics={}
    for key,c in per_class.items():
        metrics[key]=dict(c,precision=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None,
            recall=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else None)
    objectives=[];fractions=[]
    for scope,classes,target in [('field23',[0,1,3],.8),('legacy_full37',[2],.8),('heads519',[2],.8)]:
        for c in classes:
            m=metrics[scope+'/'+NAMES[c]]
            for name in ('precision','recall'):
                value=m[name];fraction=min((value or 0.)/target,1.)
                objectives.append(dict(scope=scope,cls=NAMES[c],metric=name,value=value,target=target,passed=value is not None and value>=target))
                fractions.append(fraction)
    field=counts['field23']
    joint=field['exact_positive_images']/field['positive_images'] if field['positive_images'] else 0.
    objectives.append(dict(scope='field23',metric='all_given_targets_correct_no_extra_boxes_on_positive_image',value=joint,target=.8,passed=joint>=.8))
    fractions.append(min(joint/.8,1.))
    empty_specificity=1-field['empty_with_predictions']/field['empty_images'] if field['empty_images'] else 0.
    objectives.append(dict(scope='field23',metric='empty_image_no_false_alarm_rate',value=empty_specificity,target=.8,passed=empty_specificity>=.8))
    fractions.append(min(empty_specificity/.8,1.))
    # Empty frames are reported separately and never inflate object/image success.
    fitness=.8*min(fractions)+.2*float(np.mean(fractions))
    return dict(fitness=fitness,fitness_formula='0.8*minimum(target-normalized P/R and positive-image exact rate)+0.2*mean; cap each at1',
        all_requested_development_targets_passed=all(o['passed'] for o in objectives),objectives=objectives,
        per_class=metrics,counts={k:dict(v) for k,v in counts.items()},field_positive_image_exact_rate=joint,
        thresholds=THRESHOLDS,nms_iou=.45,matching_iou=.5,validation_used_for_selection=True,
        independent_test_accuracy_not_certified=True,weights_or_gradients_not_updated_from_validation=True)


def assess_file(path,tag):
    return assess([json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()],tag)


class TargetSelector:
    def __init__(self,records,run,batch=32):
        self.records=[r for r in records if r['group']!='train'];assert len(self.records)==579
        self.run=Path(run);self.batch=batch;self.epoch=None;self.seen=set();self.latest=None
        self.images=[]
        for r in self.records:
            im=cv2.imdecode(np.frombuffer(Path(r['materialized_image']).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
            assert im.shape==(224,224,3)
            self.images.append(torch.from_numpy(np.ascontiguousarray(im[...,::-1].transpose(2,0,1))))

    def set_epoch(self,epoch):self.epoch=int(epoch)

    @torch.no_grad()
    def evaluate(self,model):
        device=next(model.parameters()).device;model.float().eval()
        self.current_model=model
        detect=model.model[-1]
        canonical=torch.as_tensor(model.yaml['anchors'],device=device,dtype=detect.anchors.dtype).view_as(detect.anchors)/detect.stride.to(device).view(-1,1,1)
        detect.anchors.copy_(canonical)
        detect.grid=[torch.empty(0,device=device) for _ in range(detect.nl)]
        detect.anchor_grid=[torch.empty(0,device=device) for _ in range(detect.nl)]
        result=[]
        for start in range(0,len(self.records),self.batch):
            images=torch.stack(self.images[start:start+self.batch]).to(device).float()/255.
            raw=model(images)[0].float().cpu().numpy();assert raw.shape[1:]==(3087,9)
            for index,output in enumerate(raw):
                r=self.records[start+index]
                truth=[[int(c),(x-w/2)*640,(y-h/2)*640-80,(x+w/2)*640,(y+h/2)*640-80] for c,x,y,w,h in r['truth224']]
                result.append(dict(id=r['id'],scope=r['validation_scope'],truth=truth,
                    classes=[2,3] if r['scope']=='head_only_partial' else [0,1,2,3],predictions=decode224(output[None]).tolist()))
        return assess(result)

    def install(self,train,callbacks):
        self.old_val=train.val.run;self.old_fitness=train.fitness
        callbacks.register_action('on_train_epoch_end','round4_epoch',self.set_epoch)
        def model_saved(last,epoch,final_epoch,best_fitness,fi):
            if float(best_fitness)!=float(fi):return
            from copy import deepcopy
            model=deepcopy(self.current_model).float().cpu().eval()
            for parameter in model.parameters():parameter.requires_grad_(False)
            dest=self.run/'weights/best_deploy_fp32.pt'
            torch.save(dict(model=model,ema=None,optimizer=None,epoch=int(epoch),best_fitness=float(fi)),dest)
            record=dict(epoch=int(epoch),fitness=float(fi),model_state_sha256=state_sha(model),
                exact_fp32_checkpoint_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                selection='fixed224 target80 bottleneck',assessment=self.latest)
            (self.run/'TARGET_BEST.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        callbacks.register_action('on_model_save','round4_target_best',model_saved)
        def wrapped_val(*a,**kw):
            result=self.old_val(*a,**kw)
            if self.epoch is not None and self.epoch not in self.seen:
                model=kw.get('model');assert model is not None
                assessment=self.evaluate(model);self.latest=assessment;self.seen.add(self.epoch)
                self.run.mkdir(parents=True,exist_ok=True)
                with (self.run/'TARGET_SELECTION.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(dict(epoch=self.epoch,**assessment),ensure_ascii=False)+'\n')
                print('ROUND4_TARGET_FITNESS',self.epoch,assessment['fitness'],'ALL_TARGETS_PASS',assessment['all_requested_development_targets_passed'],flush=True)
                for c in ('ebike','rider','bare_head'):
                    m=assessment['per_class']['field23/'+c];print('CAMPUS224',c,'TP/FP/FN',m['tp'],m['fp'],m['fn'],'P/R',m['precision'],m['recall'],flush=True)
            return result
        def fitness(_):
            assert self.latest is not None,'No fixed224 target validation has run'
            return np.array([self.latest['fitness']])
        train.val.run=wrapped_val;train.fitness=fitness

    def restore(self,train):train.val.run=self.old_val;train.fitness=self.old_fitness
