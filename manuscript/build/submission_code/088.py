"""Run each already-defined mechanism on the identical rounding stress cases."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TASKS={
 'round02_parallax':'BASE,HOMING,PARALLAX',
 'round03_refresh':'BASE,REFRESH,REFRESH_PARALLAX',
 'round04_shared':'BASE,REFRESH,REFRESH_PARALLAX,SHARED,SHARED_PARALLAX',
 'round05_strip':'BASE,STRIP',
 'round06_belief_tour':'BASE,NEAREST_HOMING,TOUR_HOMING,NEAREST_SHARED_PARALLAX,TOUR_SHARED_PARALLAX',
 'round07_reception_bracket':'BASE,RECEPTION_BRACKET',
 'round08_survey':'BASE,SURVEY',
 'round09_information':'BASE,TOUR_SHARED_PARALLAX,GATED_TOUR_SHARED_PARALLAX',
 'round10_continuous_cover':'BASE,TOUR_SHARED_PARALLAX,COVER_TOUR_SHARED_PARALLAX',
}

def task(pair):
    folder,variants=pair
    with (ROOT/folder/'stress.log').open('w') as f:
        cmd=[sys.executable,'-m','paper_evidence.q3_mechanism_reset_20260912.experiment',
             '--round',folder,'--variants',variants,'--rounding','pre_round_stress']
        subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    print(folder,'finished',flush=True)

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(task,TASKS.items()))
