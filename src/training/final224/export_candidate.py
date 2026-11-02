"""Export one fixed224 four-class candidate and verify PyTorch/TorchScript/ncnn parity.

These floating references feed later INT8/mixed precision calibration and FPGA rebuild.
No old bitstream, scale table or embedded weights are silently reused.
"""
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
import torch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'evaluation_support'))
from parity_support import decode224
from board_model_runtime import compare_detections

NAMES=['ebike','rider','helmet_head','bare_head']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def tensor(path):
    im=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
    assert im.shape==(224,224,3)
    return np.ascontiguousarray(im[...,::-1].transpose(2,0,1)[None],dtype=np.float32)/np.float32(255.)


class RawModel(torch.nn.Module):
    def __init__(self,model):super().__init__();self.model=model
    def forward(self,x):return self.model(x)[0]


def parity(a,b):
    assert a.shape==b.shape==(1,3087,9) and a.dtype==b.dtype==np.float32
    assert np.isfinite(a).all() and np.isfinite(b).all()
    result=dict(max_coordinate_error=float(np.max(np.abs(a[...,:4]-b[...,:4]))),
        max_score_error=float(np.max(np.abs(a[...,4:]-b[...,4:]))),
        coordinates_pass=bool(np.allclose(a[...,:4],b[...,:4],atol=.02,rtol=1e-4)),
        scores_pass=bool(np.allclose(a[...,4:],b[...,4:],atol=2e-5,rtol=2e-4)),
        detections_pass=bool(compare_detections(decode224(a),decode224(b))))
    assert all(result[k] for k in ('coordinates_pass','scores_pass','detections_pass')),result
    return result


def export(weight,records,dest,calibration_ids,probe_ids):
    import pnnx
    import ncnn
    assert importlib.metadata.version('pnnx')=='20260526'
    assert importlib.metadata.version('ncnn')=='1.0.20260526'
    dest.mkdir(parents=True,exist_ok=False);torch.set_num_threads(2);cv2.setNumThreads(1)
    before=sha(weight)
    checkpoint=torch.load(weight,map_location='cpu',weights_only=False)
    model=(checkpoint.get('ema') or checkpoint['model']).float().eval()
    names=list(model.names.values()) if isinstance(model.names,dict) else list(model.names)
    assert names==NAMES and model.model[-1].nc==4
    model.model[-1].export=True
    original=RawModel(model).eval();fused=RawModel(copy.deepcopy(model).fuse().eval()).eval()
    example=torch.zeros(1,3,224,224)
    with torch.no_grad():assert original(example).shape==(1,3087,9);fused(example)
    trace=torch.jit.trace(fused,example,strict=False,check_trace=True)
    ts=dest/'best_224.torchscript.pt';trace.save(str(ts));loaded=torch.jit.load(str(ts),map_location='cpu').eval()
    stage=dest/'converter';stage.mkdir()
    cmd=[str(pnnx.EXEC_PATH),str(ts.resolve()),'inputshape=[1,3,224,224]','device=cpu','fp16=0','optlevel=2',
        'pnnxparam='+str((stage/'best.pnnx.param').resolve()),'pnnxbin='+str((stage/'best.pnnx.bin').resolve()),
        'pnnxpy='+str((stage/'best_pnnx.py').resolve()),'pnnxonnx='+str((stage/'best.pnnx.onnx').resolve()),
        'ncnnparam='+str((dest/'best.ncnn.param').resolve()),'ncnnbin='+str((dest/'best.ncnn.bin').resolve()),
        'ncnnpy='+str((stage/'best_ncnn.py').resolve())]
    result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=300)
    (dest/'CONVERSION.log').write_text(result.stdout,encoding='utf-8');assert result.returncode==0,result.stdout[-4000:]
    net=ncnn.Net();net.opt.use_vulkan_compute=False;net.opt.num_threads=2
    net.opt.use_packing_layout=False;net.opt.use_fp16_storage=False;net.opt.use_fp16_arithmetic=False
    assert net.load_param(str(dest/'best.ncnn.param'))==0 and net.load_model(str(dest/'best.ncnn.bin'))==0
    inputs=net.input_names();outputs=net.output_names();assert len(inputs)==len(outputs)==1
    byid={r['id']:r for r in records};checks=[]
    for i,name in enumerate(probe_ids):
        r=byid[name];assert r['group']=='train'
        path=Path(r['materialized_image']);assert sha(path)==r['image_sha256'];x=tensor(path)
        with torch.no_grad():a=original(torch.from_numpy(x)).numpy().copy();b=loaded(torch.from_numpy(x)).numpy().copy()
        ex=net.create_extractor();ex.set_light_mode(True)
        assert ex.input(inputs[0],ncnn.Mat(x[0]).clone())==0
        ret,out=ex.extract(outputs[0]);assert ret==0
        c=np.array(out,dtype=np.float32).reshape(1,3087,9).copy()
        checks.append(dict(id=name,torchscript=parity(a,b),ncnn=parity(a,c)))
        if i<6:
            ref=dest/'fpga_reference';ref.mkdir(exist_ok=True)
            with torch.no_grad():
                y0=model.model[0](torch.from_numpy(x));y1=model.model[1](y0)
            assert tuple(y0.shape)==(1,16,112,112) and tuple(y1.shape)==(1,32,56,56)
            np.savez_compressed(ref/(name+'.npz'),input=x,after_layer0=y0.numpy(),after_layer1=y1.numpy(),output=a)
    params={}
    for i in (0,1):
        layer=fused.model.model[i].conv
        params[f'layer{i}_weight']=layer.weight.detach().numpy();params[f'layer{i}_bias']=layer.bias.detach().numpy()
    assert params['layer0_weight'].shape==(16,3,6,6) and params['layer1_weight'].shape==(32,16,3,3)
    np.savez_compressed(dest/'fpga_reference/first_two_fused_weights.npz',**params)
    calibration=dest/'calibration';(calibration/'images').mkdir(parents=True)
    manifest=[]
    for name in calibration_ids:
        r=byid[name];assert r['group']=='train'
        p=Path(r['materialized_image']);assert sha(p)==r['image_sha256']
        target=calibration/'images'/(name+'.png');shutil.copyfile(p,target)
        manifest.append(dict(id=name,sha256=sha(target),source='training_only',scope=r['scope'],image='images/'+target.name))
    assert len(manifest)==128
    save(calibration/'MANIFEST.json',manifest)
    save(dest/'MODEL_INTERFACE.json',dict(input=[1,3,224,224],output=[1,3087,9],names=NAMES,
        source_checkpoint_sha256=before,torchscript_sha256=sha(ts),ncnn_input=inputs[0],ncnn_output=outputs[0],
        ncnn_param_sha256=sha(dest/'best.ncnn.param'),ncnn_bin_sha256=sha(dest/'best.ncnn.bin'),
        raw_output='decoded cx,cy,w,h,objectness,4 class probabilities; no extra sigmoid',
        precision='FP32 floating reference for subsequent INT8/mixed calibration',
        preprocessing='already frozen nearest224x168 pad28 at114, RGB NCHW float32 /255 once',
        int8_calibration_completed=False,new_fpga_bit_hwh_generated=False,new_embedded_constants_generated=False,
        old_bitstream_not_assumed_compatible_with_new_weights=True,board_performance_not_measured=True))
    save(dest/'EXPORT_VERIFICATION.json',dict(status='PYTORCH_TORCHSCRIPT_NCNN_FIXED224_PARITY_PASS_NOT_INT8_OR_BOARD_ACCEPTANCE',
        probes=checks,calibration_images=128,calibration_from_training_only=True,fpga_layer_reference_shapes_checked=True,
        class_order_and_output_preserved=True,converter_version='20260526',ncnn_version='1.0.20260526',
        original_checkpoint_unchanged=sha(weight)==before))
    assert sha(weight)==before
    return dict(torchscript=str(ts),ncnn_param=str(dest/'best.ncnn.param'),ncnn_bin=str(dest/'best.ncnn.bin'),
        export_parity_passed=True,int8_and_matching_FPGA_stage_pending=True)
