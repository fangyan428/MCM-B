"""Seal local deliverables without touching original recommendations or cloud."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
for p in sorted(ROOT.rglob('__pycache__'),key=lambda p:len(p.parts),reverse=True):
 if p.is_dir():shutil.rmtree(p)
archive=ROOT/'candidate_source.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted((ROOT/'final_validation/code_snapshot').rglob('*')):
  if p.is_file():z.write(p,p.relative_to(ROOT/'final_validation/code_snapshot'))
 for name in ['candidate_matrix.json','best_candidate.json','validation_lock/lock.json','validation_lock/selection_snapshot.txt','README.md','REPRODUCE.md','FINAL_REPORT.md','FINAL_STATISTICS.json','FINAL_EVIDENCE.json']:
  z.write(ROOT/name,Path('paper_evidence/q4_mechanism_reset_20260912')/name)
 for p in sorted((ROOT/'reporting').glob('*.py')):
  z.write(p,Path('paper_evidence/q4_mechanism_reset_20260912/reporting')/p.name)
 for p in sorted((ROOT/'qa').glob('*.py')):
  z.write(p,Path('paper_evidence/q4_mechanism_reset_20260912/qa')/p.name)
 for name in ['SOURCE_AUDIT.md','COVERAGE_REVIEW.md','SCHEDULING_REVIEW.md','qa/FINAL_ADVERSARIAL_REVIEW.md','qa/LOCAL_ADVERSARIAL.md','qa/REPLAY.md','reporting/WORST_CASE.md']:
  z.write(ROOT/name,Path('paper_evidence/q4_mechanism_reset_20260912')/name)
 z.writestr('requirements.txt','numpy==2.4.4\nscipy==1.17.1\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 package=dict(sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),entries=len(z.namelist()),bytes=archive.stat().st_size,crc_passed=True,includes_raw_experiments=False)
(ROOT/'package_verification.json').write_text(json.dumps(package,indent=2)+'\n')
excluded={'ARTIFACT_SHA256.json','artifact_verification.json'}
files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts]
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(ROOT/'ARTIFACT_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
verification=dict(files=len(files),bytes=sum(p.stat().st_size for p in files),manifest_sha256=hashlib.sha256((ROOT/'ARTIFACT_SHA256.json').read_bytes()).hexdigest(),all_artifacts_hashed=True,original_source_unchanged=json.loads((ROOT/'PROVENANCE_CHECK.json').read_text())['original_files_changed']==[],package=package)
(ROOT/'artifact_verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification))
