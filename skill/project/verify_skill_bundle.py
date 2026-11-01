#!/usr/bin/env python3
"""Verify skill/ payload hashes and required per-item entry files; no devices accessed."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'_shared/tools'))
from verify_manifest import verify


def main():
    try:
        result=verify(ROOT,ROOT/'manifest.json')
        catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
        items=catalog['project_skills']+catalog['generic_skills']
        missing=[]
        for item in items:
            for name in ['SKILL.md','README.md','agents/openai.yaml']:
                if not (ROOT/item['path']/name).is_file():missing.append(item['path']+'/'+name)
        result.update(project_skills=len(catalog['project_skills']),generic_skills=len(catalog['generic_skills']),
                      missing_entry_files=missing,scope='Offline skill files only; not model or board acceptance.')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if not result['problems'] and not missing else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc),'hardware_accessed':False},ensure_ascii=False));return 2


if __name__=='__main__':sys.exit(main())
