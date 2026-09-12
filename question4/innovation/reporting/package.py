"""Package local candidate runtime and all experiment evidence; never uploads."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path('question4/innovation')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def archive(path, files):
    if path.exists():
        raise FileExistsError(path)
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for file in sorted(set(files)):
            output.write(file, file.as_posix())
    checksum = digest(path)
    path.with_suffix(path.suffix+'.sha256').write_text(f'{checksum}  {path.name}\n')
    with zipfile.ZipFile(path) as source:
        assert source.testzip() is None
    return dict(file=str(path), bytes=path.stat().st_size, sha256=checksum,
                entries=len(set(files)), zip_crc_verified=True)


def main():
    output = ROOT/'releases'; output.mkdir(exist_ok=True)
    snapshot = ROOT/'results/final_validation/code_snapshot'
    # Include exact runtime paths plus human decisions, configs and the frozen
    # final lock. Large raw experiments remain in the complete evidence archive.
    lock = json.loads((ROOT/'results/final_validation/lock.json').read_text())
    runtime = [Path(name) for name in lock['code_sha256']]
    runtime += list(ROOT.glob('*.md'))+list(ROOT.glob('*.json'))+list(ROOT.glob('*.csv'))
    runtime += list((ROOT/'configs').glob('*.json'))+list((ROOT/'locks').rglob('*'))
    runtime += list((ROOT/'reporting').glob('*.py'))+list((ROOT/'reporting').glob('*.txt'))
    runtime += list((ROOT/'figures').glob('*'))+[Path('question4/requirements.txt')]
    # Include self tests referred to by REPRODUCE, not just the runtime hash list.
    runtime += list(Path('question4/tests').glob('*.py'))
    runtime += [ROOT/'results/final_validation'/name for name in ('lock.json','configs.json','selection_snapshot.txt','fixtures.json')]
    runtime = [p for p in runtime if p.is_file() and '__pycache__' not in p.parts]
    small = archive(output/'q4_directional_candidate.zip', runtime)
    print(json.dumps(small), flush=True)
    evidence = [p for p in ROOT.rglob('*') if p.is_file() and 'releases' not in p.parts
                and '__pycache__' not in p.parts and not p.name.endswith('.writing')]
    full = archive(output/'q4_directional_complete_evidence.zip', evidence)
    manifest = dict(candidate=small, complete_evidence=full, uploaded=False)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(full), flush=True)


if __name__ == '__main__':
    main()
