from __future__ import annotations

import json
from datetime import datetime

import mintapi
import pandas as pd

import net_worth_tracker as nwt

MINT_DATA_FOLDER = "mint_data"


def get_mint() -> mintapi.Mint:
    email = nwt.utils.get_password("email", "mint")
    password = nwt.utils.get_password("password", "mint")
    mint = mintapi.Mint(email, password)  # Takes about ≈1m30s
    return mint


def update_data(mint: mintapi.Mint, folder: str = MINT_DATA_FOLDER) -> None:
    # Get account information
    account_data = mint.get_account_data()
    # Get transactions
    transaction_data = mint.get_transaction_data(include_investment=True)
    # Get budget information
    budget_data = mint.get_budget_data()

    for name, data in [
        ("account_data", account_data),
        ("transaction_data", transaction_data),
        ("budget_data", budget_data),
    ]:
        prefix = f"{name}."
        fname = nwt.utils.fname_from_date(folder, prefix=prefix)
        with fname.open("w") as f:
            json.dump(data, f, indent=4)


def load_latest_data(folder: str = MINT_DATA_FOLDER) -> dict[str, pd.DataFrame]:
    data = {}
    for name in ["account_data", "transaction_data", "budget_data"]:
        fname = nwt.utils.latest_fname(folder, prefix=f"{name}.")
        with fname.open("r") as f:
            df = pd.read_json(f)

            # Convert date strings to datetime
            date_cols = list(df.columns[df.columns.str.contains("Date")])
            if "date" in df.columns:
                date_cols.append("date")
            for col in date_cols:
                df[col] = pd.to_datetime(df[col])

            data[name] = df
    return data


def get_investments(
    transaction_data: pd.DataFrame, ignore_before: str | datetime = "2022-02-01"
) -> pd.DataFrame:
    df = transaction_data
    df.sort_values(by="date", inplace=True)
    investments = df[df.type == "InvestmentTransaction"]
    investments.loc[:, "amount_cumsum"] = investments.amount.cumsum()
    # Do not consider transactions before ignore_before
    investments = investments[investments.date >= ignore_before]
    first = investments.iloc[0]
    investments["ndays"] = (investments.date - first.date).dt.days
    return investments
