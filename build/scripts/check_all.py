"""Check all offline release and skill entrypoints from the repository root."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
commands=[['build/scripts/verify_release.py'],['skill/verify_skill_bundle.py'],['skill/run_offline_checks.py'],
          ['skill/_shared/tools/verify_release.py','--root','.']]
for args in commands:subprocess.run([sys.executable]+args,cwd=ROOT,check=True)
print('ALL_OFFLINE_CHECKS_PASS; no devices accessed')
