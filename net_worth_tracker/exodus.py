import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pandas as pd


@lru_cache
def get_exodus(csv_fname: str = "~/Desktop/exodus-exports/"):
    csv = sorted(Path(csv_fname).expanduser().glob("*csv"))[-1]
    balances = defaultdict(float)
    df = pd.read_csv(csv)
    for i, row in df.iterrows():
        if isinstance(row.INCURRENCY, str) or not math.isnan(row.INCURRENCY):
            balances[row.INCURRENCY] += row.INAMOUNT
        if isinstance(row.OUTCURRENCY, str) or not math.isnan(row.OUTCURRENCY):
            balances[row.OUTCURRENCY] += row.OUTAMOUNT + row.FEEAMOUNT

    return {k: v for k, v in balances.items() if v > 0}
