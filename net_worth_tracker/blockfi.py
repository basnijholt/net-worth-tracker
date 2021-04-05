from functools import lru_cache

import pandas as pd


@lru_cache
def get_blockfi_balances(csv_fname: str = "~/Downloads/transactions.csv"):
    print("Download csv from https://app.blockfi.com/settings/reports")
    df = pd.read_csv(csv_fname)
    summed = df.groupby("Cryptocurrency").sum()
    return {i: {"amount": row.Amount} for i, row in summed.iterrows()}
