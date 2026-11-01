#!/usr/bin/env python3
"""Index actual archived predictions; never add, remove or render detection boxes."""
import argparse
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile, BadZipFile

NAMES=['ebike','rider','helmet_head','bare_head']


def inspect_boxes(array,required,source,image,variant=None,record_id=None):
    import numpy as np
    a=np.asarray(array)
    if a.ndim!=2 or a.shape[1]!=6 or a.dtype.kind not in 'iuf':raise ValueError('Expected numeric Nx6 xyxy_score_class array')
    if not np.isfinite(a).all():raise ValueError('Nonfinite detection data')
    labels=a[:,5]
    if not np.equal(labels,np.floor(labels)).all() or ((labels<0)|(labels>=len(NAMES))).any():raise ValueError('Unknown class IDs')
    classes=set(labels.astype(int))
    if not set(required).issubset(classes):return None
    return {'source':source,'image':image,'variant':variant,'record_id':record_id,
            'classes_present':[NAMES[i] for i in sorted(classes)],
            'all_detections_xyxy_score_class':a.tolist(),'needs_visual_review':True,
            'proof_scope':'Class co-occurrence only, not visual correctness or accuracy acceptance.'}


def find(source,required,variant=None):
    import numpy as np
    source=Path(source);candidates=[];scanned=0;errors=[]
    if variant and variant.lower() in {'reference','truth','ground_truth','groundtruth','annotations'}:
        raise ValueError('Manual reference/ground-truth is not a model prediction variant')
    if not source.exists():raise ValueError('Source does not exist')
    if source.is_file() and source.suffix.lower()=='.zip':
        with ZipFile(source) as z:
            names=set(z.namelist())
            for name in sorted(names):
                if not name.endswith('_boxes.npy') or 'mock' in name.lower():continue
                scanned+=1
                if z.getinfo(name).file_size>8*1024*1024:
                    errors.append({'entry':name,'error':'oversized_detection_array'});continue
                try:
                    a=np.load(io.BytesIO(z.read(name)),allow_pickle=False)
                    img=name.replace('_boxes.npy','_view.jpg')
                    r=inspect_boxes(a,required,str(source)+'::'+name,
                                    str(source)+'::'+img if img in names else None)
                    if r:candidates.append(r)
                except (OSError,ValueError,TypeError,EOFError) as e:errors.append({'entry':name,'error':str(e)})
    elif source.is_file() and source.suffix.lower()=='.jsonl':
        with source.open(encoding='utf-8') as f:
            for line_no,line in enumerate(f,1):
                if not line.strip():continue
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('Prediction record must be an object')
                    tag=row.get('variant');data=row.get('predictions')
                    if variant and isinstance(row.get(variant),dict):
                        tag=variant;data=row[variant].get('predictions')
                    elif variant and tag!=variant:continue
                    if data is None:continue
                    scanned+=1
                    a=np.asarray(data,dtype=np.float64)
                    if a.size==0:a=np.empty((0,6),dtype=np.float64)
                    r=inspect_boxes(a,required,str(source)+':'+str(line_no),row.get('image',row.get('path')),tag,row.get('id'))
                    if r:candidates.append(r)
                except (ValueError,TypeError,KeyError) as e:errors.append({'line':line_no,'error':str(e)})
    elif source.is_dir():
        for p in sorted(source.rglob('*_boxes.npy')):
            if 'mock' in p.as_posix().lower():continue
            scanned+=1
            try:
                if p.stat().st_size>8*1024*1024:raise ValueError('oversized_detection_array')
                a=np.load(p,allow_pickle=False)
                img=p.with_name(p.name.replace('_boxes.npy','_view.jpg'))
                r=inspect_boxes(a,required,str(p),str(img) if img.exists() else None)
                if r:candidates.append(r)
            except (OSError,ValueError,TypeError,EOFError) as e:errors.append({'entry':str(p),'error':str(e)})
    else:raise ValueError('Provide a result directory, ZIP, or prediction JSONL')
    return {'required_classes':[NAMES[i] for i in required],'scanned_prediction_arrays':scanned,
            'candidate_count':len(candidates),'candidates':candidates,'errors':errors,
            'images_modified':False,'hardware_accessed':False,
            'note':'No candidates is a valid outcome. Truth/reference annotations are not predictions.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--require',nargs='+',choices=NAMES,default=['ebike','rider','bare_head'])
    ap.add_argument('--variant');a=ap.parse_args()
    try:
        r=find(a.source,[NAMES.index(x) for x in a.require],a.variant)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if not r['errors'] else 1
    except (OSError,ValueError,TypeError,ImportError,BadZipFile,EOFError) as e:print(json.dumps({'error':str(e)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
