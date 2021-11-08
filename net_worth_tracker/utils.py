import base64
import configparser
import contextlib
import datetime
import getpass
import json
from collections import defaultdict
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

import keyring
import pandas as pd
from currency_converter import CurrencyConverter
from keyrings.cryptfile.cryptfile import CryptFileKeyring

DEFAULT_CONFIG = Path("~/.config/crypto_etf.conf").expanduser()
RENAMES = {
    "BTCB": "BTC",
    "WBNB": "BNB",
    "beltBNB": "BNB",
    "iBTC": "BTC",
    "iETH": "ETH",
    "BETH": "ETH",
    "beltETH": "ETH",
    "WETH": "ETH",
    "WMATIC": "MATIC",
}


def base64_encode(x: str):
    message_bytes = x.encode("ascii")
    base64_bytes = base64.b64encode(message_bytes)
    return base64_bytes.decode("ascii")


def base64_decode(x: str):
    base64_bytes = x.encode("ascii")
    message_bytes = base64.b64decode(base64_bytes)
    return message_bytes.decode("ascii")


def get_password(key: str, service: str):
    config = read_config()
    try:
        cryptfile_pw = config.get("cryptfile", "password")
    except configparser.NoSectionError:
        cryptfile_pw = None

    if cryptfile_pw is not None:
        # See https://github.com/frispete/keyrings.cryptfile#example-session
        # on how to set pws.
        kr = CryptFileKeyring()
        kr.keyring_key = base64_decode(cryptfile_pw)
        pw = kr.get_password(service, key)
        if not pw:
            code = f"import net_worth_tracker as nwt; nwt.utils.set_password('{service}', '{key}')"
            raise Exception(f'Use:\npython -c "{code}"')
    else:
        pw = keyring.get_password(service, key)
        if not pw:
            raise Exception(f"python -m keyring set {service} {key}")

    return pw


def set_password(service, key, cryptfile_pw=None):
    kr = CryptFileKeyring()
    if cryptfile_pw is None:
        config = read_config()
        cryptfile_pw = config["cryptfile"]["password"]
        kr.keyring_key = base64_decode(cryptfile_pw)
    kr.set_password(service, key, getpass.getpass("Secret: "))


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

        [cryptfile]
        password = ...

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


def fname_from_date(folder, date=None, ext=".json") -> Path:
    if date is None:
        date = datetime.datetime.now()
    dt_str = date.strftime("%Y%m%d-%H%M%S")
    fname = Path(folder) / f"{dt_str}{ext}"
    fname.parent.mkdir(exist_ok=True)
    return fname


def combine_balances(*balances_dicts):
    balances = defaultdict(lambda: defaultdict(float))
    for bal in balances_dicts:
        for coin, dct in bal.items():
            balances[coin]["amount"] += dct["amount"]
            if "value" in dct:
                balances[coin]["value"] += dct["value"]
            if "price" in dct:
                balances[coin]["price"] = dct["price"]
    return {k: dict(v) for k, v in balances.items()}


def save_data(
    balances,
    bsc,
    folder=Path("data"),
):
    data = dict(balances=balances, defi=dict(bsc=bsc))
    fname = fname_from_date(folder)
    with fname.open("w") as f:
        json.dump(data, f, indent="  ")


def load_data(folder=Path("data"), ndays: int = 365):
    fnames = sorted(Path(folder).glob("*.json"))
    datas = {}
    min_date = datetime.datetime.today() - datetime.timedelta(days=ndays)
    for fname in fnames:
        dt = datetime.datetime.strptime(fname.with_suffix("").name, "%Y%m%d-%H%M%S")
        if dt >= min_date:
            with fname.open("r") as f:
                datas[dt] = json.load(f)
    return datas


def data_to_df(date, data, ignore=(), ignore_symbols=(), renames=RENAMES):
    coin_mapping = defaultdict(list)
    ignore_symbols = set(ignore_symbols)
    for where, bals in data["balances"].items():
        if where in ignore:
            continue
        for coin, info in bals.items():
            if coin.startswith("moo"):  # ignore Beefy.Finance tokens
                continue
            if coin in ignore_symbols:
                continue
            coin = renames.get(coin, coin)
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
            if info["value"] == 0:
                continue
            ratios = {f"ratio_in_{d['where']}": d["value"] / info["value"] for d in lst}
            info.update(ratios)
        infos.append(info)

    df = pd.DataFrame(infos)
    for col in df.columns:
        if col.startswith("ratio_in"):
            df[col].fillna(0, inplace=True)
            df[col.replace("ratio_in", "value_in")] = df[col] * df["value"]
    return df


def datas_to_df(datas, ignore=(), ignore_symbols=(), renames=RENAMES):
    dfs = [
        data_to_df(date, data, ignore, ignore_symbols, renames)
        for date, data in datas.items()
    ]
    return pd.concat(dfs).sort_values("date")


def get_df(key, datas):
    df = pd.DataFrame(
        [data[key] for data in datas.values()], [date for date in datas.keys()]
    ).sort_index()
    order = df.iloc[-1].sort_values(ascending=False).index
    return df[order]


def get_df_wallet(wallet, datas):
    x_i = []
    x_j = []
    for date, data in datas.items():
        if wallet in data["balances"]:
            x_i.append({k: v["amount"] for k, v in data["balances"][wallet].items()})
            x_j.append(date)
    df = pd.DataFrame(x_i, x_j).sort_index()
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
    df_30d = at_time_ago(df, datetime.timedelta(days=30))
    df_last["1w price (%)"] = 100 * (df_last.price - df_1w.price) / df_1w.price
    df_last["24h price (%)"] = 100 * (df_last.price - df_24h.price) / df_24h.price
    df_last["30d price (%)"] = 100 * (df_last.price - df_30d.price) / df_30d.price
    df_last["ATH price (€)"] = ATH = df.groupby("symbol").max().price
    df_last["ATH value (€)"] = df.groupby("symbol").max().value
    df_last["ATL value (€)"] = df.groupby("symbol").min().value
    ATL = df.groupby("symbol").min().price
    df_last["ATH change (%)"] = 100 * (df_last.price - ATH) / ATH
    df_last["ATL change (%)"] = 100 * (df_last.price - ATL) / ATL

    return df_last


def styled_overview_df(df, min_value=1):
    df_last = overview_df(df)
    df_last = df_last[df_last.value > min_value].sort_values("value", ascending=False)
    overview = df_last[
        [
            "value",
            "amount",
            "price",
            "24h price (%)",
            "1w price (%)",
            "30d price (%)",
            "ATH change (%)",
            "ATL change (%)",
            "ATH price (€)",
            "ATH value (€)",
        ]
    ]

    def color_negative_red(val):
        """
        Takes a scalar and returns a string with
        the css property `'color: red'` for negative
        strings, black otherwise.
        """
        color = "red" if val < 0 else "green"
        return "color: %s" % color

    net_worth = df_last.value.sum()
    df_last["rel_part"] = 100 * df_last.value / net_worth
    df_last["cum_rel_part"] = df_last["rel_part"].cumsum()
    overview.loc[:, "value"] = df_last.apply(
        lambda x: f"€{x.value:.2f} ({x.rel_part:.1f}%, {x.cum_rel_part:.1f}%)", axis=1
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
        .bar(subset=["ATL change (%)"], color=["lightgreen"], align="left", vmax=100)
        .bar(subset=["ATH change (%)"], color=["lightcoral"], align="zero")
    )


@lru_cache
def euro_per_dollar():
    c = CurrencyConverter()
    return c.convert(1, "USD", "EUR")


def unique_dt_per_day(df):
    df = df.set_index("date", drop=False)
    return [
        df.loc[str(date).split("T")[0]].index[-1]
        for date in df.date.dt.normalize().unique()
    ]


@contextlib.contextmanager
def hide(summary="Click here"):
    import io

    from IPython.display import HTML, display

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        yield
    html = HTML(
        f"<details><summary>{summary}</summary>"
        + f.getvalue().replace("\n", "<br>")
        + "</details>"
    )
    return display(html)
