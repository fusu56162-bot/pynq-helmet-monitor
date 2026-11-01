#!/usr/bin/env python3
"""Validate YOLO label syntax and coverage. Does not infer truth from image content."""
import argparse
import json
import math
from pathlib import Path
import sys


def audit(images,labels,confirmed_empty=None,class_count=4):
    images,labels=Path(images).resolve(),Path(labels).resolve()
    if not images.is_dir() or not labels.is_dir():raise ValueError('Both image and label directories must exist')
    if type(class_count) is not int or class_count<=0:raise ValueError('class_count must be positive')
    known=set()
    if confirmed_empty is not None:
        known={s.strip().replace('\\','/') for s in Path(confirmed_empty).read_text(encoding='utf-8-sig').splitlines()
               if s.strip() and not s.lstrip().startswith('#')}
    pics=sorted(p for p in images.rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp'} and p.is_file())
    if not pics:raise ValueError('No supported image files found')
    errors=[];empty=[];confirmed=[];counts=[0]*class_count;present=set();pairs={}
    for p in pics:
        rel=p.relative_to(images);name=rel.as_posix();present.add(name)
        lp=labels/rel.with_suffix('.txt')
        pair_key=rel.with_suffix('').as_posix()
        if pair_key in pairs:
            errors.append({'image':name,'reason':'multiple_images_share_one_label','other':pairs[pair_key]})
        pairs[pair_key]=name
        if not lp.exists():
            if name in known:confirmed.append(name)
            else:errors.append({'image':name,'reason':'missing_label_not_confirmed_empty'})
            continue
        lines=lp.read_text(encoding='utf-8-sig').splitlines()
        real=[(i+1,s.strip()) for i,s in enumerate(lines) if s.strip()]
        if not real:empty.append(name)
        if real and name in known:errors.append({'image':name,'reason':'confirmed_empty_has_nonempty_labels'})
        for line_no,line in real:
            try:
                f=line.split()
                if len(f)!=5:raise ValueError('expected_five_fields')
                if not f[0].isdigit():raise ValueError('class_id_must_be_integer')
                cls=int(f[0]);x,y,w,h=map(float,f[1:])
                if not 0<=cls<class_count:raise ValueError('class_id_out_of_range')
                if not all(math.isfinite(v) for v in [x,y,w,h]):raise ValueError('nonfinite_coordinate')
                if not(0<=x<=1 and 0<=y<=1 and 0<w<=1 and 0<h<=1):raise ValueError('invalid_normalized_xywh')
                if min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6:raise ValueError('box_outside_image')
                counts[cls]+=1
            except ValueError as e:errors.append({'image':name,'line':line_no,'reason':str(e)})
    for name in sorted(known-present):errors.append({'image':name,'reason':'confirmed_empty_not_in_images'})
    return {'format_validation_passed':not errors,'images':len(pics),'class_counts':counts,
            'missing_but_confirmed_empty':confirmed,'empty_label_files_requiring_visual_confirmation':empty,
            'errors':errors,'semantic_labels_verified':False,
            'note':'No pixel content examined; class-name mapping and split leakage require separate review.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--images',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--confirmed-empty',type=Path);ap.add_argument('--classes',type=int,default=4)
    a=ap.parse_args()
    try:
        r=audit(a.images,a.labels,a.confirmed_empty,a.classes);print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if r['format_validation_passed'] else 1
    except (OSError,ValueError,TypeError) as e:print(json.dumps({'error':str(e)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
