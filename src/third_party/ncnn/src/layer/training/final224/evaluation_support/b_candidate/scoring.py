"""Supplied-annotation matching, not an independent expert accuracy certificate."""
import numpy as np
from .geometry import iou

def match(pred,truth,classwise=True):
    pairs=[]
    for ti,t in enumerate(truth):
        for pi,p in enumerate(pred):
            if classwise and int(t[0])!=int(p[5]):continue
            overlap=iou(t[1:],p[:4])
            if overlap>=.5:pairs.append((overlap,ti,pi))
    pairs.sort(key=lambda v:-v[0])
    # YOLOv5-style confidence-independent IoU matching: one prediction/one GT.
    seen=set();one=[]
    for pair in pairs:
        if pair[2] not in seen:one.append(pair);seen.add(pair[2])
    seen=set();result=[]
    for pair in one:
        if pair[1] not in seen:result.append(pair);seen.add(pair[1])
    return result

def score(predictions,ground_truth,classes):
    pred=np.array([r for r in predictions if int(r[5]) in classes],np.float32).reshape(-1,6)
    truth=np.array([r for r in ground_truth if int(r[0]) in classes],np.float32).reshape(-1,5)
    pairs=match(pred,truth);used_pred={p[2] for p in pairs};used_gt={p[1] for p in pairs}
    hp=[r for r in pred if int(r[5]) in (2,3)];ht=[r for r in truth if int(r[0]) in (2,3)]
    head_pairs=match(hp,ht,classwise=False)
    confused=[{'truth_class':int(ht[t][0]),'predicted_class':int(hp[p][5]),'IoU':float(v)} for v,t,p in head_pairs if int(ht[t][0])!=int(hp[p][5])]
    tp=len(pairs);fp=len(pred)-tp;fn=len(truth)-tp
    return dict(tp=tp,fp=fp,fn=fn,exact_given_annotation_match=fp==0 and fn==0,
        head_misclassifications=confused,
        unmatched_predictions=[pred[i].tolist() for i in range(len(pred)) if i not in used_pred],
        missed_given_annotations=[truth[i].tolist() for i in range(len(truth)) if i not in used_gt],
        note='unmatched predictions can be real unannotated objects; requires visual adjudication')
