#!/usr/bin/env python3
"""Compute precision/recall from explicit class counts, never from confidence scores."""
import argparse
import json
from pathlib import Path
import sys


def calculate(data):
    classes=data['classes']
    if not isinstance(classes,dict) or not classes:raise ValueError('classes must be a nonempty mapping')
    result={}
    for name,c in classes.items():
        vals=[c[k] for k in ['tp','fp','fn']]
        if any(type(v) is not int or v<0 for v in vals):raise ValueError('Counts must be explicit nonnegative integers')
        tp,fp,fn=vals
        result[name]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
                      'recall':tp/(tp+fn) if tp+fn else None}
    return {'classes':result,'empty_scenes_reported_separately':data.get('empty_scenes'),
            'scope':data.get('scope'),'matching_rule':data.get('matching_rule'),
            'note':'Counts are supplied evidence; this tool does not match boxes, evaluate mAP, or verify labels.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('counts',type=Path);a=ap.parse_args()
    try:print(json.dumps(calculate(json.loads(a.counts.read_text(encoding='utf-8'))),ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:print(json.dumps({'error':str(e)},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
