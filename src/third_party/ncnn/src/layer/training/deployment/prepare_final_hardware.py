"""Audit actual ARM reference bytes and stage a new constant-only FPGA variant."""
import ctypes as ct
import hashlib
import importlib.util
import io
import json
from pathlib import Path,PurePosixPath
import shutil
import stat
import struct
import subprocess
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent/'final224_chain_v1'
OLD=ROOT.parent/'conv_chain_v1'
SOURCE=Path('C:/Users/zzyzz/Desktop/训练成果/新模型224_ARM对照与FPGA参考结果_兼容修复后_20250505_033716_5906f1a3.zip')
PACKAGE=ROOT/'copyto_patch_install_test'
DATA=WORK/'reference/returned'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def initializer(a):
    if a.ndim==1:return '{'+','.join(str(int(x)) for x in a)+'}'
    return '{\n'+',\n'.join(initializer(x) for x in a)+'\n}'


def main():
    WORK.mkdir(exist_ok=False);DATA.mkdir(parents=True)
    assert sha(SOURCE)=='337b20eceb61c866d085eb3ee94879d59f67decada5e2e394fdf36cf903b176c'
    with zipfile.ZipFile(SOURCE) as z:
        assert z.testzip() is None and len(z.infolist())==61 and sum(i.file_size for i in z.infolist())==13379941
        seen=set()
        for info in z.infolist():
            p=PurePosixPath(info.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename and ':' not in info.filename
            assert not stat.S_ISLNK(info.external_attr>>16) and info.filename.casefold() not in seen
            seen.add(info.filename.casefold());assert len(p.parts)==1
            (DATA/info.filename).write_bytes(z.read(info))
    result=read(DATA/'RESULT.json');assert result['status']=='TWO_LAYER_REFERENCE_PASS_NOT_FPGA_OR_ACCURACY_ACCEPTANCE'
    assert not result['fpga_accessed'] and not result['deployment_changed'] and all(result['originals_unchanged'].values())
    assert not (DATA/'native_stderr.log').read_bytes()
    for n,h in read(PACKAGE/'FILES_SHA256.json').items():assert sha(PACKAGE/n)==h,n
    metas=[result[k] for k in ('original_arm_parameters','input_normalization_lut','input_quantization_lut','rom')]
    metas+=result['mapping_domains']
    metas += [meta for case in result['cases'] for meta in case['files'].values()]
    arrays={}
    for m in metas:
        p=DATA/m['file'];assert sha(p)==m['sha256'],m['file']
        a=np.load(p,allow_pickle=False);assert list(a.shape)==m['shape'] and str(a.dtype)==m['dtype'] and np.isfinite(a).all()
        arrays[m['file']]=a
    helper=load('new_reference_integer',OLD/'audit_reference.py')
    codec=load('new_reference_codec',PACKAGE/'codec.py')
    binary=(PACKAGE/'model/best.ncnn.bin').read_bytes()
    spec=read(PACKAGE/'SPEC.json')
    assert spec['model_sha256']=={n:sha(PACKAGE/'model'/n) for n in ('best.ncnn.param','best.ncnn.bin')}
    assert struct.unpack_from('<I',binary)[0]==struct.unpack_from('<I',binary,1864)[0]==0xd4b38
    w0=np.frombuffer(binary,np.int8,1728,4).reshape(16,12,3,3).copy()
    w1=np.frombuffer(binary,np.int8,4608,1868).reshape(32,16,3,3).copy()
    params=arrays['actual_arm_scale_bias_input_scales.npy']
    assert params[16:32].tobytes()==binary[1732:1796] and params[64:96].tobytes()==binary[6476:6604]
    assert params[96:97].tobytes()==binary[1860:1864] and params[97:98].tobytes()==binary[6732:6736]
    configs=read(DATA/'ROM_CONFIGS.json');assert configs==result['rom_configs']
    rom=arrays['exact_activation_quantization_rom.npy'];assert rom.size==4936 and rom.nbytes==19744
    domains=[];total=0
    for c,config in enumerate(configs):
        lo=int(np.minimum(w0[c].astype(np.int64),0).sum()*127)
        hi=int(np.maximum(w0[c].astype(np.int64),0).sum()*127)
        assert (lo,hi)==(config['minimum'],config['maximum'])
        mapping=arrays['channel_%02d_actual_arm_map.npy'%c]
        assert mapping.shape==(hi-lo+1,) and np.array_equal(helper.decode(config,rom,np.arange(lo,hi+1)),mapping)
        domains.append((lo,mapping));total+=mapping.size
    rebuilt_configs,rebuilt_rom=codec.compress_all(domains)
    assert rebuilt_configs==configs and np.array_equal(rebuilt_rom,rom)
    assert total==result['mapping_complete_conservative_domain_values']==1486551
    norm=arrays['input_u8_to_float32_lut.npy'];quant=arrays['input_u8_to_int8_lut.npy']
    assert np.array_equal(norm.view(np.uint32),(np.arange(256,dtype=np.float32)/np.float32(255)).view(np.uint32))
    assert quant.min()==0 and 0<quant.max()<=127
    comparison=read(DATA/'ARM_MODEL_COMPARISON.json');assert len(comparison['cases'])==35
    sys.path.insert(0,str(PACKAGE))
    from b_candidate.scoring import score
    from parity_support import decode224
    cases_byid={r['id']:r for r in read(PACKAGE/'ARM_CASES.json')}
    import collections
    totals=collections.defaultdict(collections.Counter)
    for row in comparison['cases']:
        source=cases_byid[row['id']];assert row['truth']==source['truth']
        for tag in ('outdoor_recover5','new_fp32','new_mixed'):
            assert score(row[tag]['predictions'],row['truth'],[0,1,2,3])==row[tag]['score']
            if row['scope']=='field23':
                for cls in range(4):
                    part=score(row[tag]['predictions'],row['truth'],[cls])
                    totals[tag+'/'+str(cls)].update({k:part[k] for k in ('tp','fp','fn')})
        if row['scope']=='export_probe12':
            full=np.load(DATA/(source['case']+'_new_arm_full.npy'),allow_pickle=False)
            assert np.array_equal(decode224(full),np.asarray(row['new_mixed']['predictions'],np.float32).reshape(-1,6))
    for key,c in totals.items():assert dict(c)=={k:comparison['per_class'][key][k] for k in ('tp','fp','fn')}
    audited_cases=[]
    for record in result['cases']:
        key=record['id']
        def get(name):return arrays[record['files'][name]['file']]
        raw=get('raw');assert raw.tobytes()==np.load(PACKAGE/'inputs'/(key+'_input.npy'),allow_pickle=False).tobytes()
        u8=np.rint(raw[0]*255).astype(np.uint8);assert norm[u8].tobytes()==raw[0].tobytes()
        q0=quant[u8].reshape(3,112,2,112,2).transpose(0,2,4,1,3).reshape(12,112,112)
        assert np.array_equal(q0,get('reorg_q0'))
        sums0=helper.convolution(q0,w0,1);assert np.array_equal(sums0,get('conv0_sum'))
        q1=np.stack([helper.decode(configs[c],rom,sums0[c]) for c in range(16)])
        assert np.array_equal(q1,get('conv1_input_q1'))
        sums1=helper.convolution(q1,w1,2);assert np.array_equal(sums1,get('conv1_sum'))
        assert get('silu1_boundary').tobytes()==get('reconstructed_silu1').tobytes()
        assert get('full_original').tobytes()==get('full_resumed').tobytes()==np.load(DATA/(key+'_new_arm_full.npy'),allow_pickle=False).tobytes()
        audited_cases.append(dict(case=key,independent_sum0_values=sums0.size,independent_q1_values=q1.size,
            independent_sum1_values=sums1.size,full_resume_byte_exact=True))
    save(WORK/'reference/AUDIT.json',dict(status='INDEPENDENT_NEW_ARM_REFERENCE_AUDIT_PASS',source=str(SOURCE),source_sha256=sha(SOURCE),
        files_sha256={p.name:sha(p) for p in DATA.iterdir()},mapping_values=total,rom_words=rom.size,rom_bytes=rom.nbytes,
        source_model_sha256=spec['model_sha256'],cases=audited_cases,arm_comparison_rescored=True,
        no_new_FPGA_executed=True,accuracy80_not_passed=True))
    print('INDEPENDENT_ARM_AUDIT_PASS',total,'mapping values',flush=True)

    # Keep the exact proven source structure, replace immutable trained constants.
    hls=WORK/'hls_float_chain_compact';tail=WORK/'float_tail'
    for folder in ('src','sim','generated','fixtures'):(hls/folder).mkdir(parents=True)
    (tail/'generated').mkdir(parents=True);(tail/'validation').mkdir()
    for name in ('src/chain_float.cpp','src/chain_float.h','sim/tb_chain_float.cpp'):
        shutil.copy2(OLD/'hls_float_chain_compact'/name,hls/name)
    for name in ('tail_math.h','host_tail.cpp'):shutil.copy2(OLD/'float_tail'/name,tail/name)
    padded=np.zeros((32,18,9),np.int8);padded[:,:16]=w1.reshape(32,16,9)
    fields=('minimum','maximum','table_minimum','table_maximum','first','count','shift')
    header='// New trained final224 constants, independently audited actual ARM reference.\n'
    header+='// Model binary SHA256: '+sha(PACKAGE/'model/best.ncnn.bin')+'\n#ifndef CHAIN_MODEL_DATA_H\n#define CHAIN_MODEL_DATA_H\n'
    header+='struct ChainRomConfig { int minimum, maximum, table_minimum, table_maximum; unsigned first, count, shift; };\n'
    header+='static const signed char INPUT_QUANT[256] = '+initializer(quant)+';\n'
    header+='static const unsigned ACTIVATION_ROM['+str(rom.size)+'] = '+initializer(rom)+';\n'
    header+='static const ChainRomConfig ROM_CONFIG[16] = {\n'+',\n'.join('{'+','.join(str(c[f]) for f in fields)+'}' for c in configs)+'};\n'
    header+='static const signed char WEIGHTS0[16][12][9] = '+initializer(w0.reshape(16,12,9))+';\n'
    header+='static const signed char WEIGHTS1[32][18][9] = '+initializer(padded)+';\n#endif\n'
    (hls/'generated/model_data.h').write_text(header,encoding='ascii')
    text='// Actual ARM new model coefficients, preserve IEEE32 bits exactly.\n#ifndef RIDER_TAIL_CONSTANTS_H\n#define RIDER_TAIL_CONSTANTS_H\n'
    for name,values in [('TAIL_SCALE_BITS',params[32:64]),('TAIL_BIAS_BITS',params[64:96])]:
        text+='static const unsigned '+name+'[32] = {'+','.join(hex(int(v))+'u' for v in values.view(np.uint32))+'};\n'
    estimates=[(((1<<19)//(2*a+1)+1)//2)&255 for a in range(256,512)]
    text+='static const unsigned char RECIP_ESTIMATE[256] = {'+','.join(map(str,estimates))+'};\n#endif\n'
    (tail/'generated/tail_constants.h').write_text(text,encoding='ascii')
    compiler='C:/AMDDesignTools/2026.1/tps/mingw/10.0.0/win64.o/nt/bin/g++.exe'
    dll=tail/'validation/tail_host.dll'
    subprocess.run([compiler,'-std=c++11','-O3','-fno-fast-math','-ffp-contract=off','-shared','-static-libgcc','-static-libstdc++',str(tail/'host_tail.cpp'),'-o',str(dll)],check=True)
    library=ct.CDLL(str(dll));library.tail_host.argtypes=[ct.c_int,ct.c_void_p,ct.c_void_p,ct.c_void_p]
    for key in ('case_01','case_02'):
        sums=np.load(DATA/(key+'_conv1_sum.npy'),allow_pickle=False).transpose(1,2,0).copy()
        pre=np.empty(sums.shape,np.uint32);out=np.empty(sums.shape,np.uint32)
        library.tail_host(sums.size,sums.ctypes.data,pre.ctypes.data,out.ctypes.data)
        assert pre.tobytes()==np.load(DATA/(key+'_conv1_pre.npy'),allow_pickle=False).transpose(1,2,0).copy().tobytes()
        assert out.tobytes()==np.load(DATA/(key+'_silu1_boundary.npy'),allow_pickle=False).transpose(1,2,0).copy().tobytes()
    fixtures=hls/'fixtures';entries=[];small=[];rng=np.random.default_rng(20261026)
    def fixture(name,u8,expected=None):
        _,rh,rw=u8.shape;hh,ww=rh//2,rw//2
        q0=quant[u8].reshape(3,hh,2,ww,2).transpose(0,2,4,1,3).reshape(12,hh,ww)
        sum0=helper.convolution(q0,w0,1)
        q1=np.stack([helper.decode(configs[c],rom,sum0[c]) for c in range(16)])
        sum1=helper.convolution(q1,w1,2)
        sums=sum1.transpose(1,2,0).copy();pre=np.empty(sums.shape,np.uint32);out=np.empty(sums.shape,np.uint32)
        library.tail_host(sums.size,sums.ctypes.data,pre.ctypes.data,out.ctypes.data)
        if expected is not None:assert out.tobytes()==expected.transpose(1,2,0).copy().tobytes()
        u8.transpose(1,2,0).copy().tofile(fixtures/(name+'.rgb.u8'))
        out.tofile(fixtures/(name+'.blob4_hwc.u32'))
        entries.append(f'{name} {ww} {hh}')
        if ww<=8 and hh<=8:small.append(entries[-1])
    for i,(hh,ww) in enumerate([(1,1),(2,3),(3,2),(5,7),(8,8),(7,8),(8,7)]):fixture('random_'+str(i),rng.integers(0,256,(3,hh*2,ww*2),dtype=np.uint8))
    for value in (0,255):fixture('constant_'+str(value),np.full((3,12,10),value,np.uint8))
    for key in ('case_01','case_02'):
        raw=np.load(DATA/(key+'_raw.npy'),allow_pickle=False)[0]
        fixture(key,np.rint(raw*255).astype(np.uint8),np.load(DATA/(key+'_silu1_boundary.npy'),allow_pickle=False))
    fixture('full_random',rng.integers(0,256,(3,224,224),dtype=np.uint8))
    (fixtures/'cases.txt').write_text('\n'.join(entries)+'\n',encoding='ascii')
    (fixtures/'rtl_cases.txt').write_text('\n'.join(small)+'\n',encoding='ascii')
    for c,(lo,mapping) in enumerate(domains):mapping.tofile(fixtures/('map_%02d.i8'%c))
    (fixtures/'map_domains.txt').write_text('\n'.join(str(c['minimum'])+' '+str(c['maximum']) for c in configs)+'\n',encoding='ascii')
    bench=(hls/'sim/tb_chain_float.cpp').read_text()
    needle='        if (std::string(argv[2]) == "cases.txt") {\n'
    assert bench.count(needle)==1
    verify='''        if (std::string(argv[2]) == "cases.txt") {
            std::ifstream domains((root+"/map_domains.txt").c_str());
            if (!domains) throw std::runtime_error("Missing map domains");
            long verified = 0;
            for (int channel=0;channel<16;++channel) {
                int lo,hi; domains>>lo>>hi;
                if (!domains || hi<lo) throw std::runtime_error("Invalid map domain");
                std::string suffix=channel<10?"0":"";
                suffix+=std::to_string(channel);
                std::vector<int8_t> truth=read_file<int8_t>(root+"/map_"+suffix+".i8",size_t(hi-lo+1));
                for (int x=lo;x<=hi;++x) {
                    unsigned error=0;
                    ap_int<8> value=chain_exact_map(channel,x,error);
                    if (error || value.to_int()!=int(truth[x-lo])) throw std::runtime_error("Exhaustive exact map mismatch");
                    ++verified;
                }
            }
            std::cout<<"EXHAUSTIVE_NEW_ARM_MAPPING_PASS values="<<verified<<std::endl;
'''
    (hls/'sim/tb_chain_float.cpp').write_text(bench.replace(needle,verify),encoding='ascii')
    config=(OLD/'hls_float_chain_compact/hls_config.cfg').read_text()
    config=config.replace(str(OLD/'hls_float_chain_compact').replace('\\','/'),str(hls).replace('\\','/'))
    (hls/'hls_config.cfg').write_text(config,encoding='ascii')
    save(WORK/'PREPARATION.json',dict(status='NEW_MODEL_REFERENCE_AUDITED_AND_MATCHED_HLS_SOURCE_STAGED',
        work=str(WORK),hls_config=str(hls/'hls_config.cfg'),raw_rom_bytes=rom.nbytes,mapping_values=total,
        old_compute_cpp_source_identical=(hls/'src/chain_float.cpp').read_bytes()==(OLD/'hls_float_chain_compact/src/chain_float.cpp').read_bytes(),
        old_tail_algorithm_source_identical=(tail/'tail_math.h').read_bytes()==(OLD/'float_tail/tail_math.h').read_bytes(),
        native_new_tail_vs_actual_ARM_byte_exact_values=200704,c_sim_cases=len(entries),small_RTL_cases=len(small),
        original_model_and_hardware_not_modified=True,actual_FPGA_not_tested=True,
        files_sha256={p.relative_to(WORK).as_posix():sha(p) for p in WORK.rglob('*') if p.is_file() and p.suffix!='.dll'}))
    print('MATCHED_NEW_HLS_READY',hls/'hls_config.cfg',flush=True)


if __name__=='__main__':main()
