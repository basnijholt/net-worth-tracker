import time
from collections import defaultdict
from functools import lru_cache
from typing import Optional

import requests
from bscscan import BscScan
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait

from net_worth_tracker.utils import euro_per_dollar, read_config

IGNORE_TOKENS = {"ONX"}

# Pool/vault -> coin name
LP_MAPPING = {
    "BELT-BNB BELT LP": "BELT-BNB-LP",
    "Belt Venus BLP": "Belt-Venus-BLP",
    "AUTO-WBNB Pool": "AUTO-WBNB-LP",
}
LP_MAPPING_REVERSE = {v: k for k, v in LP_MAPPING.items()}
RENAMES = {
    "Cake": "CAKE",
    "sBDO": "SBDO",
}


@lru_cache
def get_bep20_balances(my_address: Optional[str] = None, api_key: Optional[str] = None):
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
        symbol = d["tokenSymbol"]
        if symbol in IGNORE_TOKENS:
            continue
        if d["to"].lower() == my_address:
            # Incoming tokens
            sign = +1
        else:
            sign = -1
        factor = 10 ** int(d["tokenDecimal"])
        balances[symbol] += sign * float(d["value"]) / factor

    # Get BNB balance
    balances["BNB"] += float(bsc.get_bnb_balance(address=my_address)) / 1e18

    # Remove 0 or negative balances
    # TODO: why can it become negative?
    balances = {k: v for k, v in balances.items() if v > 0}
    renames = {"Belt.fi bDAI/bUSDC/bUSDT/bBUSD": "BUSD"}
    for old, new in renames.items():
        if old in balances:
            balances[new] = balances.pop(old)

    return {k: dict(amount=v) for k, v in balances.items()}


@lru_cache
def scrape_yieldwatch(
    my_address: Optional[str] = None, headless=True, timeout: int = 30
):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    with webdriver.Chrome(options=chrome_options) as driver:
        WebDriverWait(driver, timeout)
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
        WebDriverWait(driver, timeout).until(element_present)

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
                    header_text = header.text.split("\n")
                    box_name = header_text[0]
                    dollar_value = header_text[1]
                    assert "$" in dollar_value
                    dollar_value = float(dollar_value.replace(",", "").replace("$", ""))
                    # Get the columns in the box, only the first two are relevant
                    columns = content.find_elements_by_class_name(
                        "collapsing.right.aligned"
                    )
                    names = columns[0].text.split("\n")
                    amounts = columns[1].text.split("\n")
                    d = defaultdict(list)
                    for i, amount in enumerate(amounts):
                        amount, coin = amount.split(" ", 1)
                        name = names[min(i, len(names) - 1)]
                        amount = (
                            float(amount[:-1]) * 1000
                            if "k" in amount
                            else float(amount)
                        )
                        d[name].append((amount, coin))
                    d = dict(d)
                    d["dollar_value"] = dollar_value
                    infos[which][box_name] = dict(d)
    return dict(infos)


def scraped_yieldwatch_to_balances(yieldwatch):
    balances = defaultdict(lambda: defaultdict(float))
    for defi, vaults in yieldwatch.items():
        for vault, info in vaults.items():
            for (type_, amount_coin_list) in info.items():
                if type_ in ("Harvest", "dollar_value"):
                    # is already taken into account in wallet balance
                    # if Harvest, and dollar_value is used else where.
                    continue

                if vault in LP_MAPPING:
                    assert len(amount_coin_list) == 1
                    norm_coin = LP_MAPPING[vault]
                    balances[norm_coin]["value"] = (
                        info["dollar_value"] * euro_per_dollar()
                    )

                for amount, coin in amount_coin_list:
                    norm_coin = LP_MAPPING.get(vault, coin)
                    norm_coin = RENAMES.get(norm_coin, norm_coin)
                    balances[norm_coin]["amount"] += float(amount)
    balances = {k: dict(v) for k, v in balances.items()}
    for coin, info in balances.items():
        if "value" in info:
            info["price"] = info["value"] / info["amount"]
    return {k: dict(v) for k, v in balances.items()}


@lru_cache
def get_yieldwatch_balances(  # noqa: C901
    my_address: Optional[str] = None, return_raw_data: bool = False
):
    config = read_config()
    if my_address is None:
        my_address = config["bsc"]["address"]
    platforms = {
        "BeefyFinance": "beefy",
        "PancakeSwap": "pancake",
        "HyperJump": "hyperjump",
        "Blizzard": "blizzard",
        "bDollar": "bdollar",
        "Jetfuel": "jetfuel",
        "Autofarm": "auto",
        "bunny": "bunny",
        "Acryptos": "acryptos",
        "Venus": "venus",
        "CreamFinance": "cream",
        "Alpha": "alpha",
    }
    platforms_str = ",".join(platforms.values())
    url = f"https://www.yieldwatch.net/api/all/{my_address}?platforms={platforms_str}"
    for i in range(3):
        req = requests.get(url)
        response = req.json()
        if "result" in response:
            raw_data = response["result"]
            break
        elif i == 2:
            raise RuntimeError("Tried trice and failed getting YieldWatch")
        time.sleep(2)

    balances = defaultdict(lambda: defaultdict(float))
    for k, v in raw_data.items():
        if k in ("watchBalance", "currencies", "walletBalance"):
            continue
        if k not in platforms:
            print(f"the '{k}' platform was not requested in the yieldwatch url!")
        if "vaults" in v:
            for vault in v["vaults"]["vaults"]:
                if (deposit_token := vault.get("depositToken")) is not None:
                    balances[deposit_token]["amount"] += vault["currentTokens"]
                    balances[deposit_token]["price"] = (
                        vault["priceInUSDDepositToken"] * euro_per_dollar()
                    )
                if (reward_token := vault.get("rewardToken")) is not None:
                    balances[reward_token]["amount"] += vault["pendingRewards"]
                    balances[reward_token]["price"] = (
                        vault["priceInUSDRewardToken"] * euro_per_dollar()
                    )
        if "LPVaults" in v:
            for vault in v["LPVaults"]["vaults"]:
                if (deposit_token := vault.get("depositToken")) is not None:
                    balances[deposit_token]["amount"] += vault["currentTokens"]
                    balances[deposit_token]["price"] = (
                        vault["priceInUSDDepositToken"] * euro_per_dollar()
                    )
        if "staking" in v:
            for vault in v["staking"]["vaults"]:
                if (deposit_token := vault.get("depositToken")) is not None:
                    balances[deposit_token]["amount"] += float(vault["depositedTokens"])
                    balances[deposit_token]["price"] = vault["priceInUSDDepositToken"]
                for ext in ["", "1", "2", "3"]:
                    if (reward_token := vault.get(f"rewardToken{ext}")) is not None:
                        balances[reward_token]["amount"] += float(
                            vault[f"pendingRewards{ext}"]
                        )
                        balances[reward_token]["price"] = (
                            float(vault[f"priceInUSDRewardToken{ext}"])
                            * euro_per_dollar()
                        )
    balances = {
        RENAMES.get(k, k): dict(v, value=v["amount"] * v["price"])
        for k, v in balances.items()
        if v["amount"] > 0
    }
    if return_raw_data:
        return balances, raw_data
    return balances


def update_eur_balances(eur_balances, yieldwatch, balances_bsc):
    vaults = {}
    for d in yieldwatch.values():
        vaults.update(d)
    missing = balances_bsc.keys() - eur_balances.keys()
    for coin in missing:
        norm_coin = LP_MAPPING_REVERSE.get(coin, coin)
        if norm_coin in vaults:
            print(f"Found €-value of {coin} in yieldwatch data")
            eur_balances[coin] = vaults[norm_coin]["dollar_value"]
