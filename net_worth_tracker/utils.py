import datetime
import json
from collections import defaultdict
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

import keyring
import pandas as pd
from currency_converter import CurrencyConverter

DEFAULT_CONFIG = Path("~/.config/crypto_etf.conf").expanduser()


def get_password(username: str, service: str):
    pw = keyring.get_password(service, username)
    if not pw:
        raise Exception(f"python -m keyring set {service} {username}")
    return pw


def read_config(path: Path = DEFAULT_CONFIG):
    """Create a config file at ~/.config/crypto_etf.conf with the
    following information and structure:
        [binance]
        api_key = ...
        api_secret = ...

        [bsc]
        address = ...

        [bscscan]
        api_key = ...

    Uses https://docs.python.org/3/library/configparser.html
    """
    config = ConfigParser()
    config.read(DEFAULT_CONFIG)
    if config == []:
        print(
            "Create a config file at ~/.config/crypto_etf.conf with api keys \
            according to configparser."
        )
    return config


def fname_from_date(folder, ext=".json") -> Path:
    dt_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = Path(folder) / f"{dt_str}{ext}"
    fname.parent.mkdir(exist_ok=True)
    return fname


def combine_balances(*balances_dicts):
    balances = defaultdict(float)
    for bal in balances_dicts:
        for coin, amount in bal.items():
            balances[coin] += amount
    return dict(sorted(balances.items()))


def save_data(
    balances,
    bsc,
    folder=Path("data"),
):
    data = dict(balances=balances, defi=dict(bsc=bsc))
    fname = fname_from_date(folder)
    with fname.open("w") as f:
        json.dump(data, f, indent="  ")


def load_data(folder=Path("data")):
    fnames = sorted(Path(folder).glob("*.json"))
    datas = {}
    for fname in fnames:
        with fname.open("r") as f:
            dt = datetime.datetime.strptime(fname.with_suffix("").name, "%Y%m%d-%H%M%S")
            datas[dt] = json.load(f)
    return datas


def data_to_df(date, data, ignore=()):
    coin_mapping = defaultdict(list)
    for where, bals in data["balances"].items():
        if where in ignore:
            continue
        for coin, info in bals.items():
            coin_mapping[coin].append(dict(info, where=where))
    coin_mapping = dict(coin_mapping)

    infos = []
    for coin, lst in coin_mapping.items():
        info = {"symbol": coin, "date": date, "amount": sum(d["amount"] for d in lst)}
        try:
            info["value"] = sum(d["value"] for d in lst)
        except KeyError:  # not all entries have "value" key
            pass
        else:
            info["price"] = info["value"] / info["amount"]
            ratios = {f"ratio_in_{d['where']}": d["value"] / info["value"] for d in lst}
            info.update(ratios)
        infos.append(info)

    df = pd.DataFrame(infos)
    for col in df.columns:
        if col.startswith("ratio_in"):
            df[col].fillna(0, inplace=True)
            df[col.replace("ratio_in", "value_in")] = df[col] * df["value"]
    return df


def datas_to_df(datas, ignore=()):
    dfs = [data_to_df(date, data, ignore) for date, data in datas.items()]
    return pd.concat(dfs).sort_values("date")


def get_df(key, datas):
    df = pd.DataFrame(
        [data[key] for data in datas.values()], [date for date in datas.keys()]
    ).sort_index()
    order = df.iloc[-1].sort_values(ascending=False).index
    return df[order]


def get_df_wallet(wallet, datas):
    df = pd.DataFrame(
        [
            {k: v["amount"] for k, v in data["balances"][wallet].items()}
            for data in datas.values()
        ],
        [date for date in datas.keys()],
    ).sort_index()
    order = df.iloc[-1].sort_values(ascending=False).index
    return df[order]


def at_time_ago(df, time_ago):
    now = datetime.datetime.now()
    dt = now - time_ago
    i = (df.date - dt).abs().argmin()
    date = df.date.iloc[i]
    return df[df.date == date].set_index("symbol")


def overview_df(df):
    df_24h = at_time_ago(df, datetime.timedelta(hours=24))
    df_last = at_time_ago(df, datetime.timedelta(0))
    df_1w = at_time_ago(df, datetime.timedelta(days=7))
    df_last["1w price (%)"] = 100 * (df_last.price - df_1w.price) / df_1w.price
    df_last["24h price (%)"] = 100 * (df_last.price - df_24h.price) / df_24h.price
    df_last["ATH price (€)"] = ATH = df.groupby("symbol").max().price
    df_last["ATH value (€)"] = df.groupby("symbol").max().value
    df_last["ATL value (€)"] = df.groupby("symbol").min().value
    ATL = df.groupby("symbol").min().price
    df_last["ATH change (%)"] = 100 * (df_last.price - ATH) / ATH
    df_last["ATL change (%)"] = 100 * (df_last.price - ATL) / ATL

    return df_last


def styled_overview_df(df):
    df_last = overview_df(df)
    overview = df_last[
        [
            "value",
            "amount",
            "price",
            "24h price (%)",
            "1w price (%)",
            "ATH change (%)",
            "ATL change (%)",
            "ATH price (€)",
            "ATH value (€)",
        ]
    ].sort_values("value", ascending=False)

    def color_negative_red(val):
        """
        Takes a scalar and returns a string with
        the css property `'color: red'` for negative
        strings, black otherwise.
        """
        color = "red" if val < 0 else "green"
        return "color: %s" % color

    net_worth = df_last.value.sum()
    overview["value"] = overview["value"].apply(
        lambda x: f"€{x:.2f} ({100*x/net_worth:.1f}%)"
    )
    pct_cols = [c for c in overview.columns if "%" in c]
    format = {c: "{:+.2f}%" for c in pct_cols}
    format["ATH value (€)"] = "€{:.2f}"
    format["amount"] = "{:.4f}"
    for x in ["price", "ATH price (€)", "ATL price (€)"]:
        format[x] = "€{:.4f}"

    return (
        overview.style.applymap(color_negative_red, subset=pd.IndexSlice[:, pct_cols])
        .format(format, na_rep="-")
        .bar(subset=["ATL change (%)"], color=["lightgreen"], align="left")
        .bar(subset=["ATH change (%)"], color=["red"], align="zero")
    )


@lru_cache
def euro_per_dollar():
    c = CurrencyConverter()
    return c.convert(1, "USD", "EUR")
