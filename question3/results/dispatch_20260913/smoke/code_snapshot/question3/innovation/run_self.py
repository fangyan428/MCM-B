"""Direct-file entry point: replay both algorithms against the frozen baseline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from innovation.experiment import main
import question3.strategy

if Path(question3.strategy.__file__).resolve() != ROOT / 'frozen/question3/strategy.py':
    raise RuntimeError('Replay must import the frozen baseline; run this file directly.')

if __name__ == '__main__':
    main()
