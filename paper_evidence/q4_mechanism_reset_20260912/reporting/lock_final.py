"""Freeze candidate + ablations and validation design before generating truth."""
import hashlib,json,time,shutil
from pathlib import Path
from paper_evidence.q4_mechanism_reset_20260912.experiment import source_hashes,canonical_sha256,write_json,FAMILIES
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'validation_lock'
if (out/'lock.json').exists():raise RuntimeError('Refuse replacing validation lock')
configs=json.loads((ROOT/'candidate_matrix.json').read_text()); selection=(ROOT/'SELECTION.md').read_bytes()
evidence={}
for p in list(ROOT.glob('round*/development/comparison.json'))+[ROOT/'stress/results/comparison.json',ROOT/'best_candidate.json']:
 evidence[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
hashes=source_hashes()
lock=dict(schema_version=1,stage='selection_lock_without_generation',created_unix=time.time(),
 configs=configs,configs_sha256=canonical_sha256(configs),code_sha256=hashes,
 code_bundle_sha256=canonical_sha256(hashes),reference='BASE25',
 selection_sha256=hashlib.sha256(selection).hexdigest(),generator_seed=391000,generator_count=120,
 families=list(FAMILIES),error_modes=['spatial_hash','positive','negative','smooth'],
 roundings=['bounded','pre_round_stress'],failure_penalty_s=360000.,evidence_sha256=evidence,
 selected='COVER_EXCHANGE_ELASTIC',consecutive_unsuccessful_mechanisms=10)
write_json(out/'lock.json',lock);(out/'selection_snapshot.txt').write_bytes(selection)
write_json(out/'configs.json',configs)
print(json.dumps(dict(layouts_generated=0,selected=lock['selected'],code_bundle_sha256=lock['code_bundle_sha256'])))
