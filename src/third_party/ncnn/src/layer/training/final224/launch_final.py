"""Third-round small-head data candidate; reuse the existing pinned cloud environment."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
NAMES=['ebike','rider','helmet_head','bare_head']
PREVIOUS=ROOT.parent/'joint_round4'
THIRD=ROOT.parent/'joint_round3'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def copy(src,dest,expected):
    assert sha(src)==expected,'Source changed: '+str(src)
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():assert sha(dest)==expected,'Different existing file: '+str(dest)
    else:shutil.copyfile(src,dest)


def verify(base):
    assert base!=ROOT
    for home,manifest in [(ROOT,read(ROOT/'SHA256SUMS.json')),(base,read(ROOT/'BASE_REQUIRED_SHA256.json')),(PREVIOUS,read(ROOT/'PREVIOUS_REQUIRED_SHA256.json')),(THIRD,read(ROOT/'THIRD_REQUIRED_SHA256.json'))]:
        for name,h in manifest.items():
            p=(home/name).resolve()
            assert p.is_relative_to(home) and p.is_file() and sha(p)==h,'Missing/changed package file: '+name
    records=[json.loads(x) for x in (ROOT/'DATASET_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len({r['id'] for r in records})==len(records)
    assert sum(r['group']=='train' for r in records)==3289
    for r in records:
        assert (r['scope']=='head_only_partial')==r['id'].startswith('partial_')
        assert all(len(b)==5 and int(b[0])==b[0] and 0<=b[0]<4 for b in r['truth224'])
    return records


def environment(base):
    os.environ.update(YOLOv5_AUTOINSTALL='false',WANDB_MODE='disabled',WANDB_DISABLED='true',
        CLEARML_OFFLINE_MODE='1',MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
    for key,folder in [('YOLOV5_CONFIG_DIR','yolo'),('MPLCONFIGDIR','matplotlib'),('TORCH_HOME','torch')]:
        path=ROOT/'work/cache'/folder;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    sys.path[:0]=[str(ROOT/'work/export_tools'),str(base),str(base/'vendor/yolov5')]
    sys.modules['wandb']=None;sys.modules['clearml']=None


def materialize(base,records):
    import yaml
    for r in records:
        assert r['storage'] in ('base','round3','previous','addon')
        home={'base':base,'round3':THIRD,'previous':PREVIOUS,'addon':ROOT}[r['storage']]
        for kind in ('image','label'):
            source=(home/r[kind]).resolve();assert source.is_relative_to(home)
            dest=ROOT/'work/data'/('images' if kind=='image' else 'labels')/r['group']/(r['id']+('.png' if kind=='image' else '.txt'))
            copy(source,dest,r[kind+'_sha256']);r['materialized_'+kind]=str(dest)
    common=dict(path=str(ROOT/'work/data'),train='images/train',nc=4,names=NAMES)
    dataset=ROOT/'work/dataset.yaml'
    dataset.write_text(yaml.safe_dump(dict(common,val='images/val_full'),sort_keys=False),encoding='utf-8')
    configs={}
    for scope,count in [('legacy_full37',37),('field23',23),('heads519',519)]:
        selected=[r for r in records if r['group']!='train' and r['validation_scope']==scope]
        assert len(selected)==count
        listing=ROOT/'work'/(scope+'_images.txt');listing.write_text(''.join(r['materialized_image']+'\n' for r in selected),encoding='utf-8')
        target=ROOT/'work'/(scope+'.yaml');target.write_text(yaml.safe_dump(dict(common,val=str(listing)),sort_keys=False),encoding='utf-8')
        configs[scope]=target
    save(ROOT/'work/DATASET_BUILD.json',dict(train=3289,source_image_entries=3029,training_derivatives=260,
        full_scope_early_stop_val=60,separate_partial_head_val=519,no_test_data_materialized=True,
        old_packages_unchanged=True,field_validation_not_moved_into_training=True))
    return dataset,configs


def cpu_check(base,records):
    import cv2
    import numpy as np
    import torch
    import yaml
    from focused_loss import ComputeLoss
    from utils.dataloaders import create_dataloader
    torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(42)
    weight=ROOT/'weights/round4_best.pt';before=sha(weight)
    model=torch.load(weight,map_location='cpu',weights_only=False)['model'].float()
    names=list(model.names.values()) if isinstance(model.names,dict) else list(model.names)
    assert names==NAMES and model.model[-1].nc==4
    model.model[-1].export=False
    for p in model.parameters():p.requires_grad_(True)
    model.eval()
    with torch.no_grad():raw=model(torch.zeros(1,3,224,224))[0]
    assert raw.shape==(1,3087,9) and torch.isfinite(raw).all()
    chosen=[next(r for r in records if r['origin']=='field_context_scale_training_only'),
        next(r for r in records if r['origin']=='B_more_partial_train' and r['scope']=='head_only_partial'),
        next(r for r in records if r['origin']=='B_remaining_full_train' and r['scope']!='head_only_partial'),
        next(r for r in records if r['group']=='train' and r['origin']=='field' and r.get('explicit_background'))]
    tiny=ROOT/'work/cpu_tiny'
    for r in chosen:
        for kind in ('image','label'):
            copy(Path(r['materialized_'+kind]),tiny/('images' if kind=='image' else 'labels')/'train'/Path(r['materialized_'+kind]).name,r[kind+'_sha256'])
    hyp=yaml.safe_load((ROOT/'hyp.yaml').read_text(encoding='utf-8'));hyp['label_smoothing']=0.
    loader,_=create_dataloader(str(tiny/'images/train'),224,4,32,hyp=hyp,augment=False,workers=0,rect=False,shuffle=False,cache=False,prefix='FINAL224_CPU: ')
    images,targets,paths,_=next(iter(loader));assert images.shape==(4,3,224,224)
    for i,p in enumerate(paths):
        im=cv2.imdecode(np.frombuffer(Path(p).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
        assert np.array_equal(images[i].numpy(),np.ascontiguousarray(im[...,::-1].transpose(2,0,1)))
    model.hyp=hyp;model.train();loss_fn=ComputeLoss(model)
    optimizer=torch.optim.AdamW(model.parameters(),lr=hyp['lr0']);optimizer.zero_grad()
    prediction=model(images.float()/255.)
    for p in prediction:p.retain_grad()
    loss,items=loss_fn(prediction,targets,paths=paths);assert torch.isfinite(loss) and torch.isfinite(items).all()
    loss.backward()
    partial=next(i for i,p in enumerate(paths) if Path(p).name.startswith('partial_'))
    for p,indices in zip(prediction,loss_fn.target_indices):
        mask=torch.ones_like(p[partial,...,4],dtype=torch.bool)
        ib,ia,iy,ix=indices;hit=ib==partial;mask[ia[hit],iy[hit],ix[hit]]=False
        assert torch.equal(p.grad[partial,...,4][mask],torch.zeros_like(p.grad[partial,...,4][mask]))
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    optimizer.step();model.eval()
    with torch.no_grad():raw=model(images[:1].float()/255.)[0]
    assert raw.shape==(1,3087,9) and torch.isfinite(raw).all()
    import val
    val.check_font=lambda *a,**k:None
    result,maps,_=val.run(data=dict(nc=4,names=NAMES,val=str(tiny/'images/train')),model=model,dataloader=loader,
        compute_loss=loss_fn,plots=False,half=False,imgsz=224,batch_size=4,workers=0,save_dir=ROOT/'work/cpu_tiny_validation')
    assert np.isfinite(result).all() and np.isfinite(maps).all();assert sha(weight)==before
    report=dict(status='FINAL224_CPU_MIXED_BATCH_CONTRACT_PASS_NOT_CLOUD_TRAINING_OR_ACCURACY',
        input=[1,3,224,224],output=[1,3087,9],names=NAMES,loss=float(loss.detach()),
        rgb_bytes_exact_no_second_padding=True,unknown_partial_objectness_gradient_zero=True,
        optimizer_step_and_validation_executed=True,initial_weights_unchanged=True,cuda_tested=False)
    save(ROOT/'work/CPU_CHECK.json',report);print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


def finish(run,records,configs,batch,workers,device,report,recovery=False):
    import numpy as np
    import torch
    import yaml
    import val
    from utils.dataloaders import create_dataloader
    weight=run/'weights/best_deploy_fp32.pt';before=sha(weight)
    target=torch.device('cpu' if device=='cpu' else 'cuda:0')
    if target.type=='cpu':torch.set_num_threads(2)
    else:assert torch.cuda.is_available()
    checkpoint=torch.load(weight,map_location='cpu',weights_only=False)
    model=(checkpoint.get('ema') or checkpoint['model']).float().to(target).eval()
    names=list(model.names.values()) if isinstance(model.names,dict) else list(model.names)
    assert names==NAMES and model.model[-1].nc==4
    model.names=NAMES;model.model[-1].export=False;model=model.fuse().eval()
    separate={}
    for scope,path in configs.items():
        data=yaml.safe_load(path.read_text(encoding='utf-8'))
        loader,dataset=create_dataloader(data['val'],224,batch,int(model.stride.max()),workers=workers,rect=True,pad=.5,augment=False,cache=False,prefix='POST_PT_DIRECT '+scope+': ')
        assert len(dataset)=={'legacy_full37':37,'field23':23,'heads519':519}[scope]
        dest=ROOT/'work/validation'/(run.name+'_'+scope);dest.mkdir(parents=True,exist_ok=True)
        val.check_font=lambda *a,**k:None
        result,maps,_=val.run(data=data,model=model,dataloader=loader,imgsz=224,batch_size=batch,workers=workers,
            plots=False,half=False,verbose=True,save_dir=dest,conf_thres=.001,iou_thres=.6)
        assert np.isfinite(result).all() and np.isfinite(maps).all()
        separate[scope]=dict(images=len(dataset),standard_yolo_results=list(map(float,result)),per_class_map=list(map(float,maps)),
            protocol='standard rect=True,pad=.5; not fixed224 camera thresholds',no_export_module_import=True)
    save(run/'SEPARATE_VALIDATION.json',separate)
    import fixed224_check
    fixed=run/'FIXED224'
    if fixed.exists():fixed=run/('FIXED224_recheck_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    fixed224_check.run(dict(round4_initial=ROOT/'weights/round4_best.pt',final_best=weight),records,fixed,target)
    import target_selection
    status=target_selection.assess_file(fixed/'PREDICTIONS.jsonl','final_best')
    save(run/'TARGET_STATUS.json',status)
    print('FINAL224_FINAL_DEVELOPMENT_TARGETS_PASS',status['all_requested_development_targets_passed'],flush=True)
    export_ok=False
    try:
        from export_candidate import export
        ids=read(ROOT/'EXPORT_SAMPLES.json')
        export_dir=run/'MODEL_EXPORT'
        if export_dir.exists():export_dir=run/('MODEL_EXPORT_recheck_'+datetime.datetime.now().strftime('%H%M%S_%f'))
        export(weight,records,export_dir,ids['calibration_ids'],ids['probe_ids'])
        export_ok=True
    except Exception:
        import traceback
        save(run/'EXPORT_FAILURE.json',dict(traceback=traceback.format_exc(),training_weights_preserved=True,no_training_rerun_needed=True))
        print('MODEL_EXPORT_PENDING_REPAIR_WEIGHTS_SAVED',flush=True)
    assert sha(weight)==before
    save(run/'FINAL224_RUN.json',dict(report,post_validation_completed=True,recovery_validation_only=recovery,
        saved_best_sha256=before,export_completed=export_ok,accuracy_accepted=False,board_modified=False,fixed224_result=str(fixed.relative_to(run))))
    dest=ROOT/'work/exports'/('FINAL224_'+run.name+'_RESULT.zip');dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():dest=dest.with_name(dest.stem+'_rechecked_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(run.rglob('*')):
            if p.is_file():z.write(p,'run/'+str(p.relative_to(run)).replace('\\','/'))
        for p in (ROOT/'FINAL224_PLAN.json',ROOT/'work/DATASET_BUILD.json',ROOT/'SHA256SUMS.json',ROOT/'DATASET_MANIFEST.jsonl',ROOT/'provenance/SELECTION.json',ROOT/'EXPORT_SAMPLES.json'):
            z.write(p,'provenance/'+p.name)
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    print('FINAL224_FINISHED_CANDIDATE_ONLY_NOT_BOARD_ACCEPTED',flush=True)
    print('DOWNLOAD_RESULT_ZIP:',dest,flush=True)
    return dict(archive=str(dest),sha256=sha(dest),best_sha256=before)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default=str(ROOT.parent/'joint_round1'))
    parser.add_argument('--stage',choices=['verify','cpu-check','smoke','train','post-validate'],default='verify')
    parser.add_argument('--batch',type=int,default=32);parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--run');parser.add_argument('--device',choices=['0','cpu'],default='0')
    parser.add_argument('--previous',default=str(PREVIOUS))
    parser.add_argument('--third',default=str(THIRD))
    parser.add_argument('--resume-run')
    args=parser.parse_args();base=Path(args.base).resolve()
    globals()['PREVIOUS']=Path(args.previous).resolve()
    globals()['THIRD']=Path(args.third).resolve()
    records=verify(base);environment(base);dataset,configs=materialize(base,records)
    print('FINAL224_INPUT_HASH_PASS_TRAIN3289_VAL60_PLUS_HEADS519',flush=True)
    if args.stage=='verify':
        import importlib.metadata
        assert importlib.metadata.version('pnnx')=='20260526'
        assert importlib.metadata.version('ncnn')=='1.0.20260526'
        return
    import torch
    import warnings
    warnings.filterwarnings('ignore',category=FutureWarning,message=r'.*torch\.cuda\.amp.*')
    assert torch.__version__.split('+')[0]=='2.5.1','Reuse the existing pinned environment; no reinstall needed'
    if args.stage=='cpu-check':cpu_check(base,records);return
    if args.stage=='post-validate':
        assert args.run and Path(args.run).name==args.run and '..' not in args.run
        run=(ROOT/'work/runs'/args.run).resolve();assert run.parent==(ROOT/'work/runs').resolve()
        assert (run/'results.csv').is_file() and (run/'weights/last.pt').is_file()
        report=read(ROOT/'work'/(args.run+'_environment.json'))
        finish(run,records,configs,args.batch,args.workers,args.device,report,recovery=True);return
    assert args.device=='0' and torch.cuda.is_available(),'CUDA required; no silent CPU training'
    assert args.batch in (8,16,32,64) and 0<=args.workers<=8
    subprocess.run([sys.executable,str(base/'tests/test_scoped_loss.py')],check=True,cwd=base)
    import train
    train.check_git_status=lambda *a,**k:None;train.check_requirements=lambda *a,**k:None
    import utils.general
    utils.general.check_font=lambda *a,**k:None
    sys.argv=[str(base/'vendor/yolov5/train.py')];opt=train.parse_opt()
    opt.data=str(dataset);opt.weights=str(ROOT/'weights/round4_best.pt');opt.hyp=str(ROOT/'hyp.yaml')
    opt.imgsz=224;opt.batch_size=args.batch;opt.epochs=3 if args.stage=='smoke' else 150
    opt.patience=0;opt.optimizer='AdamW';opt.device='0';opt.workers=args.workers
    opt.project=str(ROOT/'work/runs');opt.name=args.stage+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    opt.exist_ok=False;opt.resume=False;opt.multi_scale=False;opt.single_cls=False;opt.noautoanchor=True
    opt.noplots=True;opt.seed=42;opt.save_period=25;opt.cos_lr=True;opt.cache='ram';opt.freeze=[0]
    before=sha(ROOT/'weights/round4_best.pt')
    report=dict(stage=args.stage,torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),
        input_side=224,names=NAMES,train_images=3289,epochs_max=opt.epochs,patience=0,
        initialization='round4 validation-selected best epoch22; smoke never replaces formal initialization',
        initial_sha256=before,old_base=str(base),previous_package=str(PREVIOUS),selection_metric='all_requested_groups_target80_fixed224_bottleneck',not_final_board_deployment=True)
    if args.resume_run:
        assert args.stage=='train' and Path(args.resume_run).name==args.resume_run and '..' not in args.resume_run
        old_run=(ROOT/'work/runs'/args.resume_run).resolve();assert old_run.parent==(ROOT/'work/runs').resolve()
        last=old_run/'weights/last.pt'
        checkpoint=torch.load(last,map_location='cpu',weights_only=False)
        assert checkpoint.get('optimizer') is not None and int(checkpoint['epoch'])>=0,'Only an interrupted, unfinished run can resume'
        opt.name=args.resume_run;opt.resume=str(last);opt.exist_ok=True
        history=old_run/'TARGET_SELECTION.jsonl'
        if history.exists():
            entries=[json.loads(x) for x in history.read_text(encoding='utf-8').splitlines()]
            kept=[r for r in entries if r['epoch']<=int(checkpoint['epoch'])]
            if len(kept)!=len(entries):
                shutil.copyfile(history,old_run/('TARGET_SELECTION_before_resume_'+datetime.datetime.now().strftime('%H%M%S_%f')+'.jsonl'))
                history.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in kept),encoding='utf-8')
    report['epochs_requested']=opt.epochs;report['early_stopping_disabled']=True
    report['resume_run']=args.resume_run
    save(ROOT/'work'/(opt.name+'_environment.json'),report)
    from focused_loss import ComputeLoss
    from target_selection import TargetSelector
    from utils.callbacks import Callbacks
    train.ComputeLoss=ComputeLoss
    callbacks=Callbacks()
    selector=TargetSelector(records,ROOT/'work/runs'/opt.name,batch=32)
    selector.install(train,callbacks)
    try:
        train.main(opt,callbacks=callbacks)
    finally:
        selector.restore(train)
    assert sha(ROOT/'weights/round4_best.pt')==before
    import csv
    completed=list(csv.DictReader((ROOT/'work/runs'/opt.name/'results.csv').open(encoding='utf-8')))
    assert len(completed)==opt.epochs,('Expected full epoch count',len(completed),opt.epochs)
    print('TRAINED_FULL_REQUESTED_EPOCHS',len(completed),flush=True)
    finish(ROOT/'work/runs'/opt.name,records,configs,args.batch,args.workers,'0',dict(report,training_finished=True,epochs_completed=len(completed)))


if __name__=='__main__':main()
