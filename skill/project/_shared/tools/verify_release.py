#!/usr/bin/env python3
"""Verify four pinned project artifacts without importing hardware drivers."""
import argparse
import json
from pathlib import Path
import sys
from verify_manifest import verify


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True,help='Root of the delivered source tree, not board filesystem root.')
    ap.add_argument('--profile',type=Path,default=Path(__file__).resolve().parents[1]/'project_profile.json')
    a=ap.parse_args()
    try:
        p=json.loads(a.profile.read_text(encoding='utf-8'))
        mapping=p['release_artifacts']
        r=verify(a.root,mapping)
        r['profile_id']=p['profile_id'];r['scope']='Four pinned new-model/bit/HWH files only; no board or full-package acceptance.'
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0 if not r['problems'] else 1
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps({'error':type(e).__name__+': '+str(e),'hardware_accessed':False},ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
