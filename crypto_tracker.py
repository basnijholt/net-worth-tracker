import datetime
import json
import math
from collections import defaultdict
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from binance.client import Client
from bscscan import BscScan
from pycoingecko import CoinGeckoAPI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_CONFIG = Path("~/.config/crypto_etf.conf").expanduser()


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


def get_binance_client() -> Client:
    config = read_config()["binance"]
    return Client(config["api_key"], config["api_secret"])


@lru_cache
def get_binance_balances():
    client = get_binance_client()
    balances = defaultdict(float)

    def normalize(coin):
        return coin if not coin.startswith("LD") else coin[2:]

    # Get wallet and savings
    latest_info = max(
        client.get_account_snapshot(type="SPOT")["snapshotVos"],
        key=lambda x: x["updateTime"],
    )["data"]
    for d in latest_info["balances"]:
        amount = float(d["free"]) + float(d["locked"])
        if amount > 0:
            balances[normalize(d["asset"])] += amount

    # Add Liquidity pool shares
    uri = "https://api.binance.com/sapi/v1/bswap/liquidity"
    pools = client._request("get", uri, True, data=dict())
    assets = [p["share"]["asset"] for p in pools]
    for d in assets:
        for coin, amount in d.items():
            amount = float(amount)
            if amount > 0:
                balances[coin] += amount

    return dict(balances)


@lru_cache
def get_blockfi_balances(
    csv_fname: str = "~/Downloads/transactions.csv",
):
    print("Download csv from https://app.blockfi.com/settings/reports")
    df = pd.read_csv(csv_fname)
    summed = df.groupby("Cryptocurrency").sum()
    return {i: row.Amount for i, row in summed.iterrows()}


@lru_cache
def get_nexo_balances(
    csv_fname: str = "~/Downloads/nexo_transactions.csv",
):
    print("Download csv from https://platform.nexo.io/transactions")
    df = pd.read_csv(csv_fname)
    summed = df[df.Type == "Deposit"].groupby("Currency").sum("Amount")
    balances = {i: row.Amount for i, row in summed.iterrows()}
    nexo = df[df.Type == "Interest"].groupby("Currency").sum("Amount")
    assert len(nexo) == 1
    balances["NEXO"] = nexo.iloc[0].Amount
    return balances


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


@lru_cache
def get_bsc_balance(my_address: Optional[str] = None, api_key: Optional[str] = None):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    if api_key is None:
        api_key = config["bscscan"]["api_key"]

    bsc = BscScan(api_key)
    my_address = my_address.lower()
    txs = bsc.get_bep20_token_transfer_events_by_address(
        address=my_address, startblock=0, endblock=999999999, sort="asc"
    )
    balances = defaultdict(float)
    for d in txs:
        if d["to"].lower() == my_address:
            # Incoming tokens
            sign = +1
        else:
            sign = -1
        balances[d["tokenSymbol"]] += sign * float(d["value"]) / 1e18

    # Get BNB balance
    balances["BNB"] += float(bsc.get_bnb_balance(address=my_address)) / 1e18

    # Remove 0 or negative balances
    # TODO: why can it become negative?
    balances = {k: v for k, v in balances.items() if v > 0}
    renames = {"Belt.fi bDAI/bUSDC/bUSDT/bBUSD": "BUSD"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)

    return balances


@lru_cache
def scrape_yieldwatch(my_address: Optional[str] = None, headless=True):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    with webdriver.Chrome(options=chrome_options) as driver:
        wait = WebDriverWait(driver, 10)
        driver.get("https://www.yieldwatch.net/")
        for letter in my_address:
            address_bar = driver.find_element_by_id("addressInputField")
            address_bar.send_keys(letter)

        icon_bar = driver.find_element_by_class_name("centered.bottom.aligned.row")
        buttons = icon_bar.find_elements_by_class_name("center.aligned.column")
        for button in buttons:
            grayscale = button.find_element_by_class_name(
                "ui.centered.image"
            ).value_of_css_property("filter")
            if grayscale == "grayscale(1)":
                button.click()

        button = driver.find_element_by_class_name("binoculars")
        button.click()

        # Wait until the next page is loaded
        element_present = presence_of_element_located((By.CLASS_NAME, "content.active"))
        WebDriverWait(driver, timeout=10).until(element_present)

        infos = defaultdict(dict)
        segments = driver.find_elements_by_class_name("ui.segment")
        for segment in segments:
            # Many elements have the "ui segment" class, only pick the ones with
            # the "accordion ui" style.
            for defi in segment.find_elements_by_class_name("accordion.ui"):
                boxes = defi.find_elements_by_class_name("ui.equal.width.grid")
                if not boxes:
                    continue
                which = defi.text.split("\n")[0]
                for box in boxes:
                    header, content = box.find_elements_by_class_name("row")
                    box_name = header.text.split("\n")[0]
                    text = content.text
                    # Fix the case "Deposit\nPending\nHarvest 0.079822 sBDO"
                    # and replace the space after "Harvest by a \n"
                    for key in ["Deposit", "Yield", "Pending", "Harvest"]:
                        text = text.replace(key + " ", key + "\n")
                    text = text.split("\n")
                    cols = []
                    for x in text:
                        if not x[0].isdigit():
                            cols.append(x)
                        else:
                            break
                    d = {}
                    # Get only the first two columns and skip the $ amounts
                    for col, x in zip(cols, text[len(cols) :][: len(cols)]):
                        # in one case `x = '159.77 BDO $181.01'`, so we fix it
                        amount_coin = x.split(" $")[0]  # e.g., now "159.77 BDO"
                        amount, coin = amount_coin.split(" ", 1)
                        d[col] = (float(amount), coin)
                    infos[which][box_name] = d
    return dict(infos)


def bsc_to_balances(bsc):
    vault_coin_mapping = {
        "BELT-BNB BELT LP": "BELT-BNB-LP",
        "Belt Venus BLP": "Belt-Venus-BLP",
    }
    coin_renames = {"Cake": "CAKE", "sBDO": "SBDO"}
    balances = defaultdict(float)
    for defi, vaults in bsc.items():
        for vault, info in vaults.items():
            for (type_, (amount, coin)) in info.items():
                if type_ == "Harvest":
                    # is already taken into account in wallet balance
                    continue
                norm_coin = vault_coin_mapping.get(vault, coin)
                norm_coin = coin_renames.get(norm_coin, norm_coin)
                balances[norm_coin] += float(amount)
    return dict(balances)


def combine_balances(*balances_dicts):
    balances = defaultdict(float)
    for bal in balances_dicts:
        for coin, amount in bal.items():
            balances[coin] += amount
    return dict(sorted(balances.items()))


def get_balances_in_euro(balances):
    balances = balances.copy()
    renames = {"IOTA": "MIOTA"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)

    cg = CoinGeckoAPI()
    coin_list = cg.get_coins_list()
    mapping = {c["symbol"].lower(): c["id"] for c in coin_list}
    reverse_mapping = {c["id"]: c["symbol"].upper() for c in coin_list}
    ids = {mapping[c.lower()] for c in balances if c.lower() in mapping}
    ids.add(mapping["busd"])
    prices = cg.get_price(ids=list(ids), vs_currencies="eur")
    prices = {reverse_mapping[k]: v["eur"] for k, v in prices.items()}

    eur_balances = {}
    for coin, amount in balances.items():
        if coin in prices:
            eur_balances[coin] = prices[coin] * amount
        elif coin == "EUR":
            eur_balances[coin] = amount
        elif coin == "Belt-Venus-BLP":
            # Mixture of USD stable coins, so assume BUSD
            eur_balances[coin] = prices["BUSD"] * amount
        else:
            print(f"Fuck, no data for {coin}")
    # Rename back
    for old, new in renames.items():
        if new in eur_balances:
            eur_balances[old] = eur_balances.pop(new)
    return dict(sorted(eur_balances.items(), key=lambda x: x[1], reverse=True))


def save_data(
    balances_binance,
    balances_blockfi,
    balances_exodus,
    balances_nexo,
    balances_trust,
    balances_bsc,
    eur_balances,
    bsc,
):
    balances_per_category = dict(
        binance=balances_binance,
        blockfi=balances_blockfi,
        exodus=balances_exodus,
        nexo=balances_nexo,
        trust=balances_trust,
        bsc=balances_bsc,
    )
    data = dict(
        balances_per_category=dict(
            binance=balances_binance,
            blockfi=balances_blockfi,
            exodus=balances_exodus,
            nexo=balances_nexo,
            trust=balances_trust,
            bsc=balances_bsc,
        ),
        balances=combine_balances(*balances_per_category.values()),
        eur_balances=eur_balances,
        defi=dict(bsc=bsc),
    )

    dt_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = dt_str + ".json"
    with open(fname, "w") as f:
        json.dump(data, f, indent="  ")
