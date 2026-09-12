"""Validate frozen bytes and run the selected candidate's self-only adversarial tests."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from innovation import test_adversarial
import question3.strategy


def main():
    if Path(question3.strategy.__file__).resolve() != ROOT / 'frozen/question3/strategy.py':
        raise RuntimeError('Run this file directly to use the frozen baseline.')
    lock = json.loads((ROOT / 'validation_lock.json').read_text(encoding='utf-8'))
    for directory, key in [(ROOT, 'code_sha256'), (ROOT / 'frozen', 'baseline_sha256')]:
        for name, digest in lock[key].items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Locked source changed: ' + name)
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_adversarial)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
