import math
from math import hypot
import numpy as np
from src.ps.matching import maximum_weight_matching
def tensor(frame,side):
    import cv2
    if frame.shape[:2]!=(480,640):
        frame=cv2.resize(frame,(640,480),interpolation=cv2.INTER_LINEAR)
    h=side*3//4
    pad=(side-h)//2
    canvas=np.full((side,side,3),114,np.uint8)
    canvas[pad:pad+h]=cv2.resize(frame,(side,h),interpolation=cv2.INTER_NEAREST)
    return np.ascontiguousarray(canvas[...,::-1].transpose(2,0,1),dtype=np.float32)/np.float32(255)

def decode(raw,thresholds):
    from src.ps.yolo_runtime import decode as old_decode
    if raw.shape==(1,3087,9):
        expanded=np.zeros((1,6300,9),np.float32)
        expanded[:,:3087]=raw
        expanded[:,:3087,:4]*=np.float32(320/224)
        raw=expanded
    return old_decode(raw,thresholds,.45,restore=True,max_det=300)

def iou(a,b):
    x1,y1=max(a[0],b[0]),max(a[1],b[1])
    x2,y2=min(a[2],b[2]),min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    return inter/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)
def expanded(box,mode):
    x1,y1,x2,y2=box;w=x2-x1;h=y2-y1
    if mode=='rider':
        return [x1-.35*w,y1-.12*h,x2+.35*w,y1+.65*h]
    if mode=='vehicle_body':
        return [x1-.12*w,y1-1.15*h,x2+.12*w,y2+.08*h]
    return [x1-.15*w,y1-.15*h,x2+.15*w,y2+.10*h]
def merge_heads(predictions, overlap=.45):
    a=np.asarray(predictions,np.float32).reshape(-1,6)
    order=np.argsort(-a[:,4],kind='stable') if len(a) else []
    kept=[]
    while len(order) and len(kept)<300:
        n=int(order[0]);kept.append(n)
        order=np.array([j for j in order[1:] if iou(a[n,:4],a[j,:4])<=overlap],dtype=int)
    return a[kept]

def merge_bodies(predictions):
    a=np.asarray(predictions,np.float32).reshape(-1,6)
    result=[]
    for cls in (0,1):
        group=a[a[:,5]==cls]
        result.extend(merge_heads(group).tolist())
    return np.asarray(result,np.float32).reshape(-1,6)

def refine_riders_with_heads(predictions,thresholds=(.35,.10,.50,.20)):
    """Extend a truncated rider box to an independently detected nearby head.

    Do not invent a person or change its confidence. Reject distant, side-by-side
    and implausibly large head candidates. This is experimental B postprocessing.
    """
    result=np.asarray(predictions,np.float32).reshape(-1,6).copy()
    heads=[p for p in result if int(p[5]) in (2,3) and p[4]>=thresholds[int(p[5])]]
    for p in result:
        if int(p[5])!=1:continue
        width=p[2]-p[0];height=p[3]-p[1]
        candidates=[]
        for head in heads:
            cx=(head[0]+head[2])/2;cy=(head[1]+head[3])/2
            hw=head[2]-head[0];hh=head[3]-head[1]
            if not (.12*width<=hw<=1.2*width and .08*height<=hh<=.65*height):continue
            if not (p[0]-.15*width<=cx<=p[2]+.15*width):continue
            if not (p[1]-.75*height<=cy<=p[1]+.35*height):continue
            candidates.append(head)
        if candidates:
            head=max(candidates,key=lambda h:h[4])
            p[:4]=[min(p[0],head[0]),min(p[1],head[1]),max(p[2],head[2]),max(p[3],head[3])]
    return result

def clean_body_duplicates(predictions):
    """Suppress repeated boxes of the same body after multi-scale refinement."""
    a=np.asarray(predictions,np.float32).reshape(-1,6)
    bodies=[]
    for cls in (0,1):
        group=a[a[:,5]==cls]
        order=list(np.argsort(-group[:,4],kind='stable'))
        while order:
            n=order.pop(0);p=group[n];bodies.append(p)
            remaining=[]
            for j in order:
                q=group[j]
                inter=max(0,min(p[2],q[2])-max(p[0],q[0]))*max(0,min(p[3],q[3])-max(p[1],q[1]))
                small=min((p[2]-p[0])*(p[3]-p[1]),(q[2]-q[0])*(q[3]-q[1]))
                centered=(abs((p[0]+p[2]-q[0]-q[2])/2)<=.40*max(p[2]-p[0],q[2]-q[0]) and
                          abs((p[1]+p[3]-q[1]-q[3])/2)<=.40*max(p[3]-p[1],q[3]-q[1]))
                if iou(p[:4],q[:4])>.45 or (small>0 and inter/small>.90 and centered):continue
                remaining.append(j)
            order=remaining
    return np.concatenate((np.asarray(bodies,np.float32).reshape(-1,6),a[np.isin(a[:,5],(2,3))]))

def proposals(predictions,policy='predicted',proposal_threshold=.08):
    """Return rectangles using model predictions or a fixed image grid only."""
    rois=[]
    if policy in ('predicted','head_proposals','head_and_grid256','combined320','combined256'):
        body=sorted((p for p in predictions if int(p[5]) in (0,1) and p[4]>=proposal_threshold),key=lambda p:-p[4])
        for p in body:
            roi=expanded(p[:4],'rider' if int(p[5])==1 else 'vehicle_body')
            x1,y1=max(0,math.floor(roi[0])),max(0,math.floor(roi[1]))
            x2,y2=min(640,math.ceil(roi[2])),min(480,math.ceil(roi[3]))
            if x2-x1<12 or y2-y1<12:continue
            box=[x1,y1,x2,y2]
            if any(iou(box,r)>.85 for r in rois):continue
            rois.append(box)
            if len(rois)>=16:break
    if policy in ('head_proposals','head_and_grid256'):
        heads=merge_heads([p for p in predictions if int(p[5]) in (2,3) and p[4]>=.02])
        for p in sorted(heads,key=lambda p:-p[4])[:20]:
            cx=(p[0]+p[2])/2;cy=(p[1]+p[3])/2
            width=min(384,max(96,8*max(p[2]-p[0],p[3]-p[1])))
            height=width*.75
            x1=int(max(0,min(640-width,round(cx-width/2))))
            y1=int(max(0,min(480-height,round(cy-height/2))))
            box=[x1,y1,int(x1+width),int(y1+height)]
            if not any(iou(box,r)>.85 for r in rois):rois.append(box)
    if policy in ('grid320','combined320'):
        rois.extend([[x,y,x+320,y+240] for y in (0,120,240) for x in (0,160,320)])
    if policy in ('grid256','combined256','head_and_grid256'):
        rois.extend([[x,y,x+256,y+192] for y in (0,144,288) for x in (0,128,256,384)])
    if not rois:
        rois=[[0,0,640,480]]
    assert all(0<=r[0]<r[2]<=640 and 0<=r[1]<r[3]<=480 for r in rois)
    return rois
def supported(person,head):
    x1,y1,x2,y2=person[:4];w=x2-x1;h=y2-y1
    cx=(head[0]+head[2])/2;cy=(head[1]+head[3])/2
    return (x1-.08*w<=cx<=x2+.08*w and y1-.08*h<=cy<=y1+.48*h and
            head[3]-head[1]<=.6*h and head[2]-head[0]<=.9*w)
def distance(person,head):
    w=max(1.,person[2]-person[0]);h=max(1.,person[3]-person[1])
    return hypot(((head[0]+head[2]-person[0]-person[2])/2)/w,
        ((head[1]+head[3])/2-(person[1]+.18*h))/h)

def select_unique_heads(predictions):
    """Suppress duplicate person hypotheses sharing their nearest head.

    Keep distinct people with distinct head evidence. Conflicting helmet classes
    for one person remain available to the existing UNKNOWN ambiguity handling.
    """
    p=np.asarray(predictions,np.float32).reshape(-1,6)
    bodies=[r for r in p if int(r[5])==1]
    heads=[r for r in p if int(r[5]) in (2,3)]
    nearest=[]
    for person in bodies:
        options=[(distance(person,h),j) for j,h in enumerate(heads) if supported(person,h)]
        nearest.append(min(options)[1] if options else None)
    kept=[]
    for i in sorted(range(len(bodies)),key=lambda i:-bodies[i][4]):
        repeated=any(nearest[i] is not None and nearest[i]==nearest[j] and iou(bodies[i][:4],bodies[j][:4])>.35
                     and bodies[i][4]<.75*bodies[j][4] for j in kept)
        if not repeated:kept.append(i)
    bodies=[bodies[i] for i in kept]
    weights=[];ambiguous=set()
    for i,person in enumerate(bodies):
        line=[max(0.,float(h[4])-.5*distance(person,h)) if supported(person,h) else 0. for h in heads]
        best={}
        for weight,head in zip(line,heads):
            if weight>0:best[int(head[5])]=max(best.get(int(head[5]),0),weight)
        if len(best)==2 and abs(best[2]-best[3])<.08:ambiguous.add(i)
        weights.append(line)
    matches=maximum_weight_matching(weights)
    keep_heads={j for i,j in matches if weights[i][j]>0}
    for i in ambiguous:
        for cls in (2,3):
            options=[(weights[i][j],j) for j,h in enumerate(heads) if int(h[5])==cls and weights[i][j]>0]
            if options:keep_heads.add(max(options)[1])
    cars=[r for r in p if int(r[5])==0]
    return np.asarray(cars+bodies+[heads[j] for j in sorted(keep_heads)],np.float32).reshape(-1,6)
