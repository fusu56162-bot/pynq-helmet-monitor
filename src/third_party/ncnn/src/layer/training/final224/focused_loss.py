"""YOLOv5 GPL-3.0 loss adaptation: emphasize small-head localization/classification.

Inference modules, class count, anchors, and output layout stay unchanged.
Partial-label objectness retains the previously checked supervision mask.
"""
from pathlib import Path
import torch
import torch.nn.functional as F
from scoped_loss import ComputeLoss as ScopedLoss
from scoped_loss import ScopedObjectness
from utils.metrics import bbox_iou
from utils.torch_utils import de_parallel


class BalancedObjectness(ScopedObjectness):
    def __call__(self,prediction,truth):
        owner=self.parent;layer=owner.layer;owner.layer+=1
        if owner.partial is None or not owner.partial.any():return self.original(prediction,truth)
        raw=F.binary_cross_entropy_with_logits(prediction,truth,pos_weight=self.original.pos_weight,reduction='none')
        mask=torch.ones_like(raw);mask[owner.partial]=0
        b,a,gy,gx=owner.target_indices[layer];mask[b,a,gy,gx]=1
        per_image=(raw*mask).flatten(1).sum(1)/mask.flatten(1).sum(1).clamp_min(1)
        weight=torch.where(owner.partial,float(owner.hyp.get('partial_obj_weight',.03)),1.).to(prediction)
        return (per_image*weight).mean()


class ComputeLoss(ScopedLoss):
    def __init__(self,model,autobalance=False):
        super().__init__(model,autobalance)
        self.BCEobj=BalancedObjectness(self,self.BCEobj.original)
        self.strides=[float(s) for s in de_parallel(model).model[-1].stride]
        self.small_head_weight=float(self.hyp.get('small_head_weight',3.0))
        self.head_weight=float(self.hyp.get('head_weight',1.5))
        assert self.hyp['fl_gamma']==0 and self.small_head_weight>=1 and self.head_weight>=1

    def __call__(self,p,targets,paths=None):
        if paths is None:raise ValueError('Annotation scope paths required')
        assert len(paths)==p[0].shape[0]
        self.layer=0
        self.partial=torch.tensor([Path(s).name.startswith('partial_') for s in paths],device=self.device)
        if targets.numel():
            part=self.partial[targets[:,0].long()]
            assert torch.all((targets[part,1]==2)|(targets[part,1]==3))
        lcls=torch.zeros(1,device=self.device);lbox=torch.zeros_like(lcls);lobj=torch.zeros_like(lcls)
        tcls,tbox,indices,anchors=self.build_targets(p,targets)
        for i,pi in enumerate(p):
            b,a,gj,gi=indices[i];tobj=torch.zeros(pi.shape[:4],dtype=pi.dtype,device=self.device)
            n=b.shape[0]
            if n:
                pxy,pwh,_,pcls=pi[b,a,gj,gi].split((2,2,1,self.nc),1)
                pxy=pxy.sigmoid()*2-.5;pwh=(pwh.sigmoid()*2)**2*anchors[i]
                iou=bbox_iou(torch.cat((pxy,pwh),1),tbox[i],CIoU=True).reshape(-1)
                head=(tcls[i]==2)|(tcls[i]==3)
                small=head&(tbox[i][:,2:].amin(1)*self.strides[i]<=12.)
                weight=torch.ones_like(iou)
                weight=torch.where(head,weight*self.head_weight,weight)
                weight=torch.where(small,torch.full_like(weight,self.small_head_weight),weight)
                lbox+=((1-iou)*weight).sum()/weight.sum()
                quality=iou.detach().clamp(0).to(tobj.dtype)
                floor=float(self.hyp.get('small_head_obj_floor',.25))
                quality=torch.where(small,floor+(1-floor)*quality,quality)
                if self.sort_obj_iou:
                    order=quality.argsort();b,a,gj,gi,quality=b[order],a[order],gj[order],gi[order],quality[order]
                if self.gr<1:quality=(1-self.gr)+self.gr*quality
                tobj[b,a,gj,gi]=quality
                if self.nc>1:
                    truth=torch.full_like(pcls,self.cn);truth[range(n),tcls[i]]=self.cp
                    each=F.binary_cross_entropy_with_logits(pcls,truth,pos_weight=self.BCEcls.pos_weight,reduction='none').mean(1)
                    lcls+=(each*weight).sum()/weight.sum()
            obji=self.BCEobj(pi[...,4],tobj)
            lobj+=obji*self.balance[i]
            if self.autobalance:self.balance[i]=self.balance[i]*.9999+.0001/obji.detach().item()
        if self.autobalance:self.balance=[x/self.balance[self.ssi] for x in self.balance]
        lbox*=self.hyp['box'];lobj*=self.hyp['obj'];lcls*=self.hyp['cls']
        return (lbox+lobj+lcls)*p[0].shape[0],torch.cat((lbox,lobj,lcls)).detach()
