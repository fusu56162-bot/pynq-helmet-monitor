#!/usr/bin/env python3
"""Run isolated host checks on archived evidence and negative fixtures; no camera or PL."""
from pathlib import Path
import hashlib
import json
import math
import sys
import tempfile
from zipfile import ZipFile
import io
import argparse

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'_shared/tools'))
checks=[]


def check(name,condition):
    if not condition:raise AssertionError(name)
    checks.append(name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temp-root',type=Path,help='Existing writable directory for isolated temporary fixtures.')
    args=parser.parse_args()
    import numpy as np
    from compare_arrays import compare_paths
    from summarize_run import summarize
    from metrics_from_counts import calculate
    from verify_manifest import verify
    from audit_yolo_labels import audit
    from check_vivado_reports import parse_reports
    from find_examples import find
    from inspect_board import parse_meminfo
    f=ROOT/'_shared/fixtures'
    pair=compare_paths(f/'golden_cpu_raw.npy',f/'golden_fpga_raw.npy')
    check('historical_cpu_fpga_pair_exact',pair['passed'] and pair['elements']==27783)
    r=summarize(json.loads((f/'camera_result_excerpt.json').read_text(encoding='utf-8')))
    check('real_48_frames_fps',r['frame_records']==48 and math.isclose(r['fps_from_complete_frame_records'],2.3866876101030634,rel_tol=1e-12))
    check('real_nested_suffix',math.isclose(r['nested_arm_suffix']['mean_ms'],187.39891918742538,rel_tol=1e-10))
    cpu=next(x for x in r['main_timers'] if x['name']=='main.cpu_reference_ms')
    check('sparse_cpu_check_amortized',cpu['events']==5 and math.isclose(cpu['amortized_per_inferred_frame_ms'],24.907208958344047,rel_tol=1e-10))
    record={'frames':[],'metrics':{'main.frame_age_before_decode_ms':{'count':1,'mean_ms':99,'total_ms':99}}}
    unknown=summarize(record)
    check('frame_age_not_summed_as_work',unknown['main_timer_sum_ms'] is None and
          unknown['nonexclusive_or_unknown_main_keys_excluded']==['main.frame_age_before_decode_ms'])
    check('missing_cleanup_stays_unknown',unknown['evidence']['dma_quiesced'] is None)
    vals=calculate(json.loads((f/'campus_counts.json').read_text(encoding='utf-8')))
    check('empty_scenes_not_object_denominator',math.isclose(vals['classes']['bare_head']['recall'],2/7) and
          math.isclose(vals['classes']['ebike']['precision'],9/11))
    zero=calculate({'classes':{'helmet_head':{'tp':0,'fp':0,'fn':0}}})
    check('no_positive_recall_is_unknown',zero['classes']['helmet_head']['recall'] is None)
    rpt=parse_reports(f/'hardware_utilization.rpt',f/'hardware_timing.rpt')
    check('real_resource_DSP178',rpt['resource']['DSP']==178)
    check('real_resource_bram30p5',rpt['resource']['BRAM_tiles']==30.5)
    check('real_slacks_and_failing_endpoints',rpt['timing']['WNS_ns']==0.949 and rpt['timing']['WHS_ns']==0.015 and
          rpt['timing']['WPWS_ns']==3.75 and all(rpt['checks'].values()))
    check('inventory_meminfo_units',parse_meminfo('CmaFree: 5 kB\n')['CmaFree_bytes']==5120)
    with tempfile.TemporaryDirectory(prefix='helmet_skill_checks_',dir=str(args.temp_root) if args.temp_root else str(ROOT)) as tmp:
        d=Path(tmp);(d/'payload.bin').write_bytes(b'original')
        digest=hashlib.sha256((d/'payload.bin').read_bytes()).hexdigest()
        m=d/'manifest.json';m.write_text(json.dumps({'payload.bin':digest}),encoding='utf-8')
        check('manifest_good',not verify(d,m)['problems'])
        (d/'payload.bin').write_bytes(b'changed')
        check('manifest_tamper_detected',verify(d,m)['problems'][0]['reason']=='sha256_mismatch')
        (d/'payload.bin').unlink()
        check('manifest_missing_detected',verify(d,m)['problems'][0]['reason']=='missing_file')
        m.write_text(json.dumps({'../outside.bin':digest}),encoding='utf-8')
        check('manifest_traversal_refused',verify(d,m)['problems'][0]['reason']=='outside_root_path')
        a,b=d/'a.npy',d/'b.npy'
        def pair_save(x,y):np.save(a,x,allow_pickle=False);np.save(b,y,allow_pickle=False)
        pair_save(np.array([0.0],np.float32),np.array([-0.0],np.float32))
        check('signed_zero_exact_rejected',not compare_paths(a,b)['passed'])
        check('explicit_zero_numeric_tolerance',compare_paths(a,b,'tolerance',0,0)['passed'])
        pair_save(np.array([np.nan],np.float32),np.array([np.nan],np.float32))
        check('matching_nan_refused',not compare_paths(a,b)['passed'])
        pair_save(np.ones(2,np.int8),np.ones(2,np.int16))
        check('dtype_mismatch_refused',not compare_paths(a,b)['passed'])
        pair_save(np.ones((1,2),np.float32),np.ones((2,1),np.float32))
        check('shape_mismatch_refused',not compare_paths(a,b)['passed'])
        try:compare_paths(a,b,'tolerance')
        except ValueError:check('implicit_tolerance_refused',True)
        else:raise AssertionError('missing tolerance accepted')
        images,labels=d/'images',d/'labels';images.mkdir();labels.mkdir()
        (images/'positive.png').write_bytes(b'not-decoded-by-format-check')
        (images/'empty.png').write_bytes(b'not-decoded-by-format-check')
        (labels/'positive.txt').write_text('3 0.5 0.5 0.2 0.2\n')
        ar=audit(images,labels)
        check('missing_label_not_automatic_empty',not ar['format_validation_passed'])
        empty=d/'confirmed.txt';empty.write_text('empty.png\n')
        check('explicit_confirmed_empty_allowed',audit(images,labels,empty)['format_validation_passed'])
        (labels/'positive.txt').write_text('9 0.5 0.5 0.2 0.2\n')
        check('wrong_class_id_rejected',not audit(images,labels,empty)['format_validation_passed'])
        (labels/'positive.txt').write_text('3 0.99 0.5 0.2 0.2\n')
        check('out_of_image_box_rejected',not audit(images,labels,empty)['format_validation_passed'])
        (labels/'positive.txt').write_text('3 nan 0.5 0.2 0.2\n')
        check('nonfinite_label_rejected',not audit(images,labels,empty)['format_validation_passed'])
        out=d/'results';out.mkdir()
        boxes=np.array([[1,1,30,30,.8,0],[2,1,20,25,.7,1],[3,2,8,8,.6,3]],np.float32)
        np.save(out/'frame_01_boxes.npy',boxes,allow_pickle=False)
        (out/'frame_01_view.jpg').write_bytes(b'unmodified-fixture')
        before=hashlib.sha256((out/'frame_01_view.jpg').read_bytes()).hexdigest()
        got=find(out,[0,1,3])
        check('three_classes_same_frame_indexed',got['candidate_count']==1 and got['candidates'][0]['needs_visual_review'])
        check('finding_does_not_modify_image',before==hashlib.sha256((out/'frame_01_view.jpg').read_bytes()).hexdigest())
        np.save(out/'frame_01_boxes.npy',boxes[:2],allow_pickle=False)
        check('missing_bare_head_not_fabricated',find(out,[0,1,3])['candidate_count']==0)
        js=d/'predictions.jsonl'
        js.write_text(json.dumps({'truth':boxes.tolist()})+'\n',encoding='utf-8')
        check('manual_truth_is_not_prediction',find(js,[0,1,3])['candidate_count']==0)
        js.write_text(json.dumps({'predictions':[[1,2,3],[4,5,6]]})+'\n',encoding='utf-8')
        check('bad_Nx6_shape_not_reshaped',bool(find(js,[0,1,3])['errors']))
        z=d/'results.zip'
        mem=io.BytesIO();np.save(mem,boxes,allow_pickle=False)
        with ZipFile(z,'w') as zipf:zipf.writestr('session/frame_01_boxes.npy',mem.getvalue())
        check('zip_prediction_indexed_without_extract',find(z,[0,1,3])['candidate_count']==1)
        broken=d/'timing.rpt';broken.write_text('no timing summary here')
        try:parse_reports(f/'hardware_utilization.rpt',broken)
        except ValueError:check('missing_timing_not_pass',True)
        else:raise AssertionError('missing timing accepted')
    print(json.dumps({'status':'OFFLINE_TOOL_CHECKS_PASS','checks_passed':len(checks),'checks':checks,
                      'board_contacted':False,'camera_started':False,'PL_programmed':False,
                      'scope':'Archived values and synthetic negative fixtures; no cross-team transfer or new board test.'},
                     ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps({'status':'OFFLINE_TOOL_CHECKS_FAILED','error':type(e).__name__+': '+str(e),
                          'checks_completed':checks},ensure_ascii=False,indent=2));sys.exit(2)
